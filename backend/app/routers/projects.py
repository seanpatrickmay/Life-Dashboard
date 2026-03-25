from __future__ import annotations

import zoneinfo
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
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
from app.db.repositories.todo_repository import TodoRepository
from app.db.session import get_session
from app.db.models.claude_code import ProjectActivity
from app.db.models.project import Project
from app.routers._shared import build_todo_response, run_project_suggestions
from app.schemas.projects import (
  ProjectActivityResponse,
  ProjectBoardResponse,
  ProjectCreateRequest,
  ProjectResponse,
  ProjectSuggestionResponse,
  ProjectUpdateRequest,
  SuggestionRecomputeRequest,
)
from app.schemas.todos import TodoCreateRequest, TodoItemResponse, TodoUpdateRequest


router = APIRouter(prefix="/projects", tags=["projects"])


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

  # Fetch last activity date per project
  from sqlalchemy import func as sa_func
  last_activity_stmt = (
    select(ProjectActivity.project_id, sa_func.max(ProjectActivity.local_date))
    .where(ProjectActivity.user_id == current_user.id)
    .group_by(ProjectActivity.project_id)
  )
  last_activity_result = await session.execute(last_activity_stmt)
  last_activity_map: dict[int, date] = {row[0]: row[1] for row in last_activity_result.all()}

  project_payload: list[ProjectResponse] = []
  for project in projects:
    open_count, completed_count = counts.get(project.id, (0, 0))
    project_payload.append(
      ProjectResponse(
        id=project.id,
        name=project.name,
        display_name=project.display_name,
        notes=project.notes,
        archived=project.archived,
        sort_order=project.sort_order,
        created_at=project.created_at,
        updated_at=project.updated_at,
        open_count=open_count,
        completed_count=completed_count,
        state_summary_json=project.state_summary_json,
        state_updated_at_utc=project.state_updated_at_utc,
        last_activity_date=last_activity_map.get(project.id),
      )
    )
  project_payload.sort(key=lambda item: (item.name != INBOX_PROJECT_NAME, item.sort_order, item.id))

  return ProjectBoardResponse(
    projects=project_payload,
    todos=[build_todo_response(todo, now_utc) for todo in todos],
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


@router.get("/activities/all", response_model=list[ProjectActivityResponse])
async def get_all_activities(
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
  since: date | None = None,
  until: date | None = None,
  page: int = 1,
  per_page: int = 50,
) -> list[ProjectActivityResponse]:
  """Unified activity feed across all projects."""
  query = (
    select(ProjectActivity, Project.name)
    .join(Project, ProjectActivity.project_id == Project.id)
    .where(ProjectActivity.user_id == current_user.id)
    .order_by(ProjectActivity.local_date.desc(), ProjectActivity.created_at.desc())
  )
  if since:
    query = query.where(ProjectActivity.local_date >= since)
  if until:
    query = query.where(ProjectActivity.local_date <= until)
  query = query.offset((page - 1) * per_page).limit(per_page)

  result = await session.execute(query)
  rows = result.all()

  return [
    ProjectActivityResponse(
      id=activity.id,
      project_id=activity.project_id,
      project_name=project_name,
      local_date=activity.local_date,
      session_id=activity.session_id,
      summary=activity.summary,
      details_json=activity.details_json,
      created_at=activity.created_at,
    )
    for activity, project_name in rows
  ]


@router.get("/{project_id}/activities", response_model=list[ProjectActivityResponse])
async def get_project_activities(
  project_id: int,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
  since: date | None = None,
  until: date | None = None,
  page: int = 1,
  per_page: int = 50,
) -> list[ProjectActivityResponse]:
  """Activity feed for a specific project."""
  query = (
    select(ProjectActivity)
    .where(
      ProjectActivity.user_id == current_user.id,
      ProjectActivity.project_id == project_id,
    )
    .order_by(ProjectActivity.local_date.desc(), ProjectActivity.created_at.desc())
  )
  if since:
    query = query.where(ProjectActivity.local_date >= since)
  if until:
    query = query.where(ProjectActivity.local_date <= until)
  query = query.offset((page - 1) * per_page).limit(per_page)

  result = await session.execute(query)
  activities = result.scalars().all()

  return [
    ProjectActivityResponse(
      id=a.id,
      project_id=a.project_id,
      local_date=a.local_date,
      session_id=a.session_id,
      summary=a.summary,
      details_json=a.details_json,
      created_at=a.created_at,
    )
    for a in activities
  ]


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
  if "display_name" in update_data:
    project.display_name = update_data["display_name"].strip() if update_data["display_name"] else None
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
    background_tasks.add_task(run_project_suggestions, current_user.id, todo_ids)
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


# ── Todo CRUD ────────────────────────────────────────────────────────────


@router.post("/todos", response_model=TodoItemResponse)
async def create_todo(
  payload: TodoCreateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> TodoItemResponse:
  """Create a todo, optionally assigned to a project."""
  project_repo = ProjectRepository(session)
  todo_repo = TodoRepository(session)

  project_id = payload.project_id
  if project_id is None:
    inbox = await project_repo.ensure_inbox_project(current_user.id)
    project_id = inbox.id

  todo = await todo_repo.create_one(
    user_id=current_user.id,
    project_id=project_id,
    text=payload.text,
    deadline=payload.deadline_utc,
    deadline_is_date_only=payload.deadline_is_date_only,
    time_horizon=payload.time_horizon,
  )
  await session.commit()
  return build_todo_response(todo, datetime.now(timezone.utc))


@router.patch("/todos/{todo_id}", response_model=TodoItemResponse)
async def update_todo(
  todo_id: int,
  payload: TodoUpdateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> TodoItemResponse:
  """Update a todo (text, completed, project, deadline, etc.)."""
  todo_repo = TodoRepository(session)
  todo = await todo_repo.get_for_user(current_user.id, todo_id)
  if todo is None:
    raise HTTPException(status_code=404, detail="Todo not found")

  update_data = payload.model_dump(exclude_unset=True)
  if "text" in update_data and update_data["text"] is not None:
    todo.text = update_data["text"].strip()
  if "project_id" in update_data and update_data["project_id"] is not None:
    todo.project_id = update_data["project_id"]
  if "deadline_utc" in update_data:
    todo.deadline_utc = update_data["deadline_utc"]
  if "deadline_is_date_only" in update_data and update_data["deadline_is_date_only"] is not None:
    todo.deadline_is_date_only = update_data["deadline_is_date_only"]
  if "time_horizon" in update_data and update_data["time_horizon"] is not None:
    todo.time_horizon = update_data["time_horizon"]
  if "completed" in update_data and update_data["completed"] is not None:
    now = datetime.now(timezone.utc)
    if update_data["completed"] and not todo.completed:
      todo.completed = True
      todo.completed_at_utc = now
      if payload.time_zone:
        local_tz = zoneinfo.ZoneInfo(payload.time_zone)
        todo.completed_local_date = now.astimezone(local_tz).date()
      else:
        todo.completed_local_date = now.date()
    elif not update_data["completed"] and todo.completed:
      todo.completed = False
      todo.completed_at_utc = None
      todo.completed_local_date = None

  await session.flush()
  await session.commit()
  return build_todo_response(todo, datetime.now(timezone.utc))


@router.delete("/todos/{todo_id}", status_code=204, response_class=Response)
async def delete_todo(
  todo_id: int,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> Response:
  """Delete a todo."""
  todo_repo = TodoRepository(session)
  todo = await todo_repo.get_for_user(current_user.id, todo_id)
  if todo is None:
    raise HTTPException(status_code=404, detail="Todo not found")
  await todo_repo.delete_for_user(current_user.id, todo_id)
  await session.commit()
  return Response(status_code=204)
