from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.quotas import enforce_chat_quota
from app.db.repositories.project_repository import ProjectRepository, TodoProjectSuggestionRepository
from app.db.repositories.todo_repository import TodoRepository
from app.db.session import AsyncSessionLocal, get_session
from app.db.models.entities import User
from app.schemas.todos import (
  TodoCreateRequest,
  TodoAssistantMessageRequest,
  TodoAssistantMessageResponse,
  TodoItemResponse,
  TodoUpdateRequest,
)
from app.services.claude_todo_agent import TodoAssistantAgent
from app.services.todo_accomplishment_agent import TodoAccomplishmentAgent
from app.services.todo_calendar_link_service import TodoCalendarLinkService
from app.services.todo_project_suggestion_service import TodoProjectSuggestionService
from app.services.async_ai_service import AsyncAIService
from app.utils.timezone import local_today, resolve_time_zone


router = APIRouter(prefix="/todos", tags=["todos"])


def _todo_response(item, now_utc: datetime) -> TodoItemResponse:
  return TodoItemResponse(
    id=item.id,
    project_id=item.project_id,
    text=item.text,
    completed=item.completed,
    completed_at_utc=item.completed_at_utc,
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


@router.get("", response_model=list[TodoItemResponse])
async def list_todos(
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
  time_zone: str | None = Query(None),
  limit: int = Query(default=50, le=200, description="Maximum items to return"),
  offset: int = Query(default=0, ge=0, description="Number of items to skip"),
) -> list[TodoItemResponse]:
  repo = TodoRepository(session)
  # Get all todos for the date (we'll paginate in memory for simplicity)
  all_items = await repo.list_for_user(current_user.id, local_date=local_today(time_zone))

  # Apply pagination
  paginated_items = all_items[offset:offset + limit]

  now_utc = datetime.now(timezone.utc)
  return [_todo_response(item, now_utc) for item in paginated_items]


@router.post("", response_model=TodoItemResponse)
async def create_todo(
  payload: TodoCreateRequest,
  background_tasks: BackgroundTasks,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> TodoItemResponse:
  repo = TodoRepository(session)
  project_repo = ProjectRepository(session)
  inbox = await project_repo.ensure_inbox_project(current_user.id)
  project_id = payload.project_id if payload.project_id is not None else inbox.id
  project = await project_repo.get_for_user(current_user.id, project_id)
  if project is None:
    raise HTTPException(status_code=404, detail="Project not found")
  todo = await repo.create_one(
    current_user.id,
    project_id,
    payload.text,
    payload.deadline_utc,
    deadline_is_date_only=payload.deadline_is_date_only,
  )
  await session.flush()
  await session.commit()
  if todo.deadline_utc is not None and not todo.completed:
    link_service = TodoCalendarLinkService(session)
    await link_service.upsert_event_for_todo(todo, time_zone=payload.time_zone)
  background_tasks.add_task(_run_project_suggestions, current_user.id, [todo.id])
  now_utc = datetime.now(timezone.utc)
  return _todo_response(todo, now_utc)


@router.patch("/{todo_id}", response_model=TodoItemResponse)
async def update_todo(
  todo_id: int,
  payload: TodoUpdateRequest,
  background_tasks: BackgroundTasks,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> TodoItemResponse:
  repo = TodoRepository(session)
  project_repo = ProjectRepository(session)
  suggestion_repo = TodoProjectSuggestionRepository(session)
  todo = await repo.get_for_user(current_user.id, todo_id)
  if todo is None:
    raise HTTPException(status_code=404, detail="Todo not found")

  update_data = payload.model_dump(exclude_unset=True)

  if "text" in update_data and update_data["text"] is not None:
    todo.text = update_data["text"].strip()

  if "project_id" in update_data and update_data["project_id"] is not None:
    project = await project_repo.get_for_user(current_user.id, int(update_data["project_id"]))
    if project is None:
      raise HTTPException(status_code=404, detail="Project not found")
    todo.project_id = project.id
    await suggestion_repo.delete_for_todo(current_user.id, todo.id)

  if "deadline_utc" in update_data:
    todo.deadline_utc = update_data["deadline_utc"]
    if update_data["deadline_utc"] is None:
      todo.deadline_is_date_only = False
  if "deadline_is_date_only" in update_data:
    todo.deadline_is_date_only = bool(update_data["deadline_is_date_only"])

  if "completed" in update_data and update_data["completed"] is not None:
    was_completed = todo.completed
    requested_completed_at = update_data.get("completed_at_utc")
    todo.mark_completed(update_data["completed"], completed_at_utc=requested_completed_at)
    if update_data["completed"]:
      tz_name = (update_data.get("time_zone") or todo.completed_time_zone or "UTC").strip() or "UTC"
      todo.completed_time_zone = tz_name
      if todo.completed_at_utc:
        zone = resolve_time_zone(tz_name)
        todo.completed_local_date = todo.completed_at_utc.astimezone(zone).date()
      if not todo.accomplishment_text:
        # Check cache first for instant response
        cached_accomplishment = AsyncAIService.get_cached_accomplishment(todo.text)
        if cached_accomplishment:
          todo.accomplishment_text = cached_accomplishment
          todo.accomplishment_generated_at_utc = datetime.now(timezone.utc)
        else:
          # Set a placeholder and generate async
          todo.accomplishment_text = f"Completed {todo.text}".strip()
          # Schedule async generation in background
          AsyncAIService.schedule_accomplishment_generation(todo.id, current_user.id, todo.text)
    elif not update_data["completed"]:
      todo.completed_local_date = None
      todo.completed_time_zone = None
  elif "completed_at_utc" in update_data and update_data["completed_at_utc"] is not None and todo.completed:
    todo.completed_at_utc = update_data["completed_at_utc"]
    tz_name = (update_data.get("time_zone") or todo.completed_time_zone or "UTC").strip() or "UTC"
    todo.completed_time_zone = tz_name
    zone = resolve_time_zone(tz_name)
    todo.completed_local_date = todo.completed_at_utc.astimezone(zone).date()
  await session.flush()
  await session.commit()
  link_service = TodoCalendarLinkService(session)
  if todo.completed:
    await link_service.unlink_todo(todo, delete_event=True)
  elif todo.deadline_utc is not None:
    await link_service.upsert_event_for_todo(todo, time_zone=payload.time_zone)
  else:
    await link_service.unlink_todo(todo, delete_event=True)
  if "text" in update_data and update_data["text"] is not None:
    background_tasks.add_task(_run_project_suggestions, current_user.id, [todo.id])
  now_utc = datetime.now(timezone.utc)
  return _todo_response(todo, now_utc)


@router.delete("/{todo_id}", status_code=204, response_class=Response)
async def delete_todo(
  todo_id: int,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> Response:
  repo = TodoRepository(session)
  todo = await repo.get_for_user(current_user.id, todo_id)
  if todo is None:
    raise HTTPException(status_code=404, detail="Todo not found")
  link_service = TodoCalendarLinkService(session)
  await link_service.unlink_todo(todo, delete_event=True)
  await repo.delete_for_user(current_user.id, todo_id)
  await session.commit()
  return Response(status_code=204)


async def _assistant_todo_message(
  payload: TodoAssistantMessageRequest,
  background_tasks: BackgroundTasks,
  current_user: User = Depends(enforce_chat_quota),
  session: AsyncSession = Depends(get_session),
) -> TodoAssistantMessageResponse:
  agent = TodoAssistantAgent(session)
  response = await agent.respond(current_user.id, payload.message, payload.session_id)
  now_utc = datetime.now(timezone.utc)
  created_items = [_todo_response(item, now_utc) for item in response.items]
  if response.items:
    background_tasks.add_task(
      _run_project_suggestions, current_user.id, [item.id for item in response.items]
    )
  return TodoAssistantMessageResponse(
    session_id=response.session_id,
    reply=response.reply,
    created_items=created_items,
    raw_payload=response.raw_payload,
  )


@router.post("/assistant/message", response_model=TodoAssistantMessageResponse)
async def todo_assistant_message(
  payload: TodoAssistantMessageRequest,
  background_tasks: BackgroundTasks,
  current_user: User = Depends(enforce_chat_quota),
  session: AsyncSession = Depends(get_session),
) -> TodoAssistantMessageResponse:
  return await _assistant_todo_message(payload, background_tasks, current_user, session)


@router.post("/claude/message", response_model=TodoAssistantMessageResponse, deprecated=True)
async def claude_todo_message(
  payload: TodoAssistantMessageRequest,
  background_tasks: BackgroundTasks,
  current_user: User = Depends(enforce_chat_quota),
  session: AsyncSession = Depends(get_session),
) -> TodoAssistantMessageResponse:
  return await _assistant_todo_message(payload, background_tasks, current_user, session)
