from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.entities import User
from app.db.models.todo import TodoItem
from app.db.repositories.project_repository import (
  INBOX_PROJECT_NAME,
  ProjectRepository,
  TodoProjectSuggestionRepository,
)
from app.db.repositories.project_note_repository import ProjectNoteRepository
from app.db.repositories.todo_repository import TodoRepository
from app.db.session import AsyncSessionLocal, get_session
from app.schemas.projects import (
  ProjectBoardResponse,
  ProjectCreateRequest,
  ProjectNoteCreateRequest,
  ProjectNoteResponse,
  ProjectResponse,
  ProjectSuggestionResponse,
  ProjectNoteUpdateRequest,
  ProjectUpdateRequest,
  SuggestionRecomputeRequest,
)
from app.schemas.todos import TodoItemResponse
from app.services.todo_project_suggestion_service import TodoProjectSuggestionService


router = APIRouter(prefix="/projects", tags=["projects"])


def _to_todo_response(item: TodoItem, now_utc: datetime) -> TodoItemResponse:
  return TodoItemResponse(
    id=item.id,
    project_id=item.project_id,
    text=item.text,
    completed=item.completed,
    deadline_utc=item.deadline_utc,
    deadline_is_date_only=item.deadline_is_date_only,
    is_overdue=bool(
      not item.completed and item.deadline_utc is not None and item.deadline_utc < now_utc
    ),
    created_at=item.created_at,
    updated_at=item.updated_at,
  )


async def _run_project_suggestions(user_id: int, todo_ids: list[int]) -> None:
  async with AsyncSessionLocal() as session:
    service = TodoProjectSuggestionService(session)
    await service.process_todo_ids(user_id=user_id, todo_ids=todo_ids)


@router.get("/board", response_model=ProjectBoardResponse)
async def get_project_board(
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> ProjectBoardResponse:
  project_repo = ProjectRepository(session)
  todo_repo = TodoRepository(session)
  suggestion_repo = TodoProjectSuggestionRepository(session)

  await project_repo.ensure_inbox_project(current_user.id)
  projects = await project_repo.list_for_user(current_user.id, include_archived=False)
  todos = await todo_repo.list_for_user(current_user.id)
  suggestions = await suggestion_repo.list_for_user(current_user.id)
  now_utc = datetime.now(timezone.utc)

  counts: dict[int, tuple[int, int]] = {}
  for todo in todos:
    open_count, completed_count = counts.get(todo.project_id, (0, 0))
    if todo.completed:
      completed_count += 1
    else:
      open_count += 1
    counts[todo.project_id] = (open_count, completed_count)

  project_payload: list[ProjectResponse] = []
  for project in projects:
    open_count, completed_count = counts.get(project.id, (0, 0))
    project_payload.append(
      ProjectResponse(
        id=project.id,
        name=project.name,
        notes=project.notes,
        archived=project.archived,
        sort_order=project.sort_order,
        created_at=project.created_at,
        updated_at=project.updated_at,
        open_count=open_count,
        completed_count=completed_count,
      )
    )
  project_payload.sort(key=lambda item: (item.name != INBOX_PROJECT_NAME, item.sort_order, item.id))

  return ProjectBoardResponse(
    projects=project_payload,
    todos=[_to_todo_response(todo, now_utc) for todo in todos],
    suggestions=[
      ProjectSuggestionResponse(
        todo_id=suggestion.todo_id,
        suggested_project_name=suggestion.suggested_project_name,
        confidence=suggestion.confidence,
        reason=suggestion.reason,
      )
      for suggestion in suggestions
    ],
  )


@router.get("/{project_id}/notes", response_model=list[ProjectNoteResponse])
async def list_project_notes(
  project_id: int,
  include_archived: bool = Query(False),
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> list[ProjectNoteResponse]:
  project_repo = ProjectRepository(session)
  note_repo = ProjectNoteRepository(session)
  project = await project_repo.get_for_user(current_user.id, project_id)
  if project is None:
    raise HTTPException(status_code=404, detail="Project not found")
  notes = await note_repo.list_for_project(
    user_id=current_user.id,
    project_id=project_id,
    include_archived=include_archived,
  )
  return [ProjectNoteResponse.model_validate(note) for note in notes]


@router.post("/{project_id}/notes", response_model=ProjectNoteResponse)
async def create_project_note(
  project_id: int,
  payload: ProjectNoteCreateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> ProjectNoteResponse:
  project_repo = ProjectRepository(session)
  note_repo = ProjectNoteRepository(session)
  project = await project_repo.get_for_user(current_user.id, project_id)
  if project is None:
    raise HTTPException(status_code=404, detail="Project not found")
  note = await note_repo.create_one(
    user_id=current_user.id,
    project_id=project_id,
    title=payload.title,
    body_markdown=payload.body_markdown,
    tags=payload.tags,
    pinned=payload.pinned,
  )
  await session.commit()
  return ProjectNoteResponse.model_validate(note)


@router.patch("/{project_id}/notes/{note_id}", response_model=ProjectNoteResponse)
async def update_project_note(
  project_id: int,
  note_id: int,
  payload: ProjectNoteUpdateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> ProjectNoteResponse:
  project_repo = ProjectRepository(session)
  note_repo = ProjectNoteRepository(session)
  project = await project_repo.get_for_user(current_user.id, project_id)
  if project is None:
    raise HTTPException(status_code=404, detail="Project not found")
  note = await note_repo.get_for_user(user_id=current_user.id, note_id=note_id)
  if note is None or note.project_id != project_id:
    raise HTTPException(status_code=404, detail="Project note not found")
  update_data = payload.model_dump(exclude_unset=True)
  if "title" in update_data and update_data["title"] is not None:
    title = update_data["title"].strip()
    if not title:
      raise HTTPException(status_code=422, detail="Note title cannot be empty")
    note.title = title
  if "body_markdown" in update_data and update_data["body_markdown"] is not None:
    note.body_markdown = update_data["body_markdown"]
  if "tags" in update_data and update_data["tags"] is not None:
    note.tags = [tag.strip() for tag in update_data["tags"] if tag.strip()]
  if "archived" in update_data and update_data["archived"] is not None:
    note.archived = bool(update_data["archived"])
  if "pinned" in update_data and update_data["pinned"] is not None:
    note.pinned = bool(update_data["pinned"])
  await session.flush()
  await session.commit()
  return ProjectNoteResponse.model_validate(note)


@router.post("", response_model=ProjectResponse)
async def create_project(
  payload: ProjectCreateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
  repo = ProjectRepository(session)
  existing = await repo.get_by_name_for_user(current_user.id, payload.name)
  if existing is not None:
    raise HTTPException(status_code=409, detail="Project with this name already exists")
  project = await repo.create_one(
    user_id=current_user.id,
    name=payload.name,
    notes=payload.notes,
    sort_order=payload.sort_order,
  )
  await session.commit()
  return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
  project_id: int,
  payload: ProjectUpdateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
  repo = ProjectRepository(session)
  project = await repo.get_for_user(current_user.id, project_id)
  if project is None:
    raise HTTPException(status_code=404, detail="Project not found")
  update_data = payload.model_dump(exclude_unset=True)
  if "name" in update_data and update_data["name"] is not None:
    name_candidate = update_data["name"].strip()
    if not name_candidate:
      raise HTTPException(status_code=422, detail="Project name cannot be empty")
    conflict = await repo.get_by_name_for_user(current_user.id, name_candidate)
    if conflict is not None and conflict.id != project.id:
      raise HTTPException(status_code=409, detail="Project with this name already exists")
    project.name = name_candidate
  if "notes" in update_data:
    project.notes = update_data["notes"].strip() if update_data["notes"] else None
  if "archived" in update_data and update_data["archived"] is not None:
    if project.name == INBOX_PROJECT_NAME and update_data["archived"]:
      raise HTTPException(status_code=400, detail="Inbox cannot be archived")
    project.archived = bool(update_data["archived"])
  if "sort_order" in update_data and update_data["sort_order"] is not None:
    project.sort_order = int(update_data["sort_order"])
  await session.flush()
  await session.commit()
  return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204, response_class=Response)
async def delete_project(
  project_id: int,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> Response:
  repo = ProjectRepository(session)
  project = await repo.get_for_user(current_user.id, project_id)
  if project is None:
    raise HTTPException(status_code=404, detail="Project not found")
  if project.name == INBOX_PROJECT_NAME:
    raise HTTPException(status_code=400, detail="Inbox cannot be deleted")

  inbox = await repo.ensure_inbox_project(current_user.id)
  await session.execute(
    update(TodoItem)
    .where(TodoItem.user_id == current_user.id, TodoItem.project_id == project.id)
    .values(project_id=inbox.id)
  )
  await session.delete(project)
  await session.commit()
  return Response(status_code=204)


@router.post("/suggestions/recompute", status_code=202)
async def recompute_suggestions(
  payload: SuggestionRecomputeRequest,
  background_tasks: BackgroundTasks,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
  project_repo = ProjectRepository(session)
  inbox = await project_repo.ensure_inbox_project(current_user.id)

  todo_ids: list[int] = []
  if payload.todo_ids:
    todo_ids = [int(value) for value in payload.todo_ids]
  elif payload.scope == "all":
    stmt = select(TodoItem.id).where(TodoItem.user_id == current_user.id)
    result = await session.execute(stmt)
    todo_ids = [row[0] for row in result.all()]
  else:
    stmt = select(TodoItem.id).where(
      TodoItem.user_id == current_user.id, TodoItem.project_id == inbox.id
    )
    result = await session.execute(stmt)
    todo_ids = [row[0] for row in result.all()]

  if todo_ids:
    background_tasks.add_task(_run_project_suggestions, current_user.id, todo_ids)
  return {"scheduled_count": len(todo_ids)}


@router.delete("/suggestions/{todo_id}", status_code=204, response_class=Response)
async def dismiss_suggestion(
  todo_id: int,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> Response:
  suggestion_repo = TodoProjectSuggestionRepository(session)
  await suggestion_repo.delete_for_todo(current_user.id, todo_id)
  await session.commit()
  return Response(status_code=204)
