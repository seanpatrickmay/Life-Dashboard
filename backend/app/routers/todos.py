from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.quotas import enforce_chat_quota
from app.db.repositories.todo_repository import TodoRepository
from app.db.session import get_session
from app.db.models.entities import User
from app.schemas.todos import (
  ClaudeTodoMessageRequest,
  ClaudeTodoMessageResponse,
  TodoCreateRequest,
  TodoItemResponse,
  TodoUpdateRequest,
)
from app.services.claude_todo_agent import ClaudeTodoAgent
from app.services.todo_accomplishment_agent import TodoAccomplishmentAgent
from app.utils.timezone import local_today, resolve_time_zone


router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=list[TodoItemResponse])
async def list_todos(
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
  time_zone: str | None = Query(None),
) -> list[TodoItemResponse]:
  repo = TodoRepository(session)
  items = await repo.list_for_user(current_user.id, local_date=local_today(time_zone))
  now_utc = datetime.now(timezone.utc)
  return [
    TodoItemResponse(
      id=item.id,
      text=item.text,
      completed=item.completed,
      deadline_utc=item.deadline_utc,
      is_overdue=bool(
        not item.completed and item.deadline_utc is not None and item.deadline_utc < now_utc
      ),
      created_at=item.created_at,
      updated_at=item.updated_at,
    )
    for item in items
  ]


@router.post("", response_model=TodoItemResponse)
async def create_todo(
  payload: TodoCreateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> TodoItemResponse:
  repo = TodoRepository(session)
  todo = await repo.create_one(current_user.id, payload.text, payload.deadline_utc)
  await session.flush()
  await session.commit()
  now_utc = datetime.now(timezone.utc)
  return TodoItemResponse(
    id=todo.id,
    text=todo.text,
    completed=todo.completed,
    deadline_utc=todo.deadline_utc,
    is_overdue=bool(
      not todo.completed and todo.deadline_utc is not None and todo.deadline_utc < now_utc
    ),
    created_at=todo.created_at,
    updated_at=todo.updated_at,
  )


@router.patch("/{todo_id}", response_model=TodoItemResponse)
async def update_todo(
  todo_id: int,
  payload: TodoUpdateRequest,
  current_user: User = Depends(get_current_user),
  session: AsyncSession = Depends(get_session),
) -> TodoItemResponse:
  repo = TodoRepository(session)
  todo = await repo.get_for_user(current_user.id, todo_id)
  if todo is None:
    raise HTTPException(status_code=404, detail="Todo not found")

  update_data = payload.model_dump(exclude_unset=True)

  if "text" in update_data and update_data["text"] is not None:
    todo.text = update_data["text"].strip()

  # Only touch the deadline if the field is present in the payload.
  # This allows explicit null to mean "no deadline", while omitting the field keeps the existing deadline.
  if "deadline_utc" in update_data:
    todo.deadline_utc = update_data["deadline_utc"]

  if "completed" in update_data and update_data["completed"] is not None:
    was_completed = todo.completed
    todo.mark_completed(update_data["completed"])
    if update_data["completed"] and not was_completed:
      tz_name = (update_data.get("time_zone") or "UTC").strip() or "UTC"
      todo.completed_time_zone = tz_name
      if todo.completed_at_utc:
        zone = resolve_time_zone(tz_name)
        todo.completed_local_date = todo.completed_at_utc.astimezone(zone).date()
      if not todo.accomplishment_text:
        agent = TodoAccomplishmentAgent(session)
        try:
          todo.accomplishment_text = await agent.rewrite(todo.text)
        except Exception as exc:  # noqa: BLE001
          logger.warning("[todos] failed to generate accomplishment: {}", exc)
          todo.accomplishment_text = f"Completed {todo.text}".strip()
        todo.accomplishment_generated_at_utc = datetime.now(timezone.utc)
    elif not update_data["completed"]:
      todo.completed_local_date = None
      todo.completed_time_zone = None
  await session.flush()
  await session.commit()
  now_utc = datetime.now(timezone.utc)
  return TodoItemResponse(
    id=todo.id,
    text=todo.text,
    completed=todo.completed,
    deadline_utc=todo.deadline_utc,
    is_overdue=bool(
      not todo.completed and todo.deadline_utc is not None and todo.deadline_utc < now_utc
    ),
    created_at=todo.created_at,
    updated_at=todo.updated_at,
  )


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
  await session.delete(todo)
  await session.commit()
  return Response(status_code=204)


@router.post("/claude/message", response_model=ClaudeTodoMessageResponse)
async def claude_todo_message(
  payload: ClaudeTodoMessageRequest,
  current_user: User = Depends(enforce_chat_quota),
  session: AsyncSession = Depends(get_session),
) -> ClaudeTodoMessageResponse:
  agent = ClaudeTodoAgent(session)
  response = await agent.respond(current_user.id, payload.message, payload.session_id)
  now_utc = datetime.now(timezone.utc)
  created_items = [
    TodoItemResponse(
      id=item.id,
      text=item.text,
      completed=item.completed,
      deadline_utc=item.deadline_utc,
      is_overdue=bool(
        not item.completed and item.deadline_utc is not None and item.deadline_utc < now_utc
      ),
      created_at=item.created_at,
      updated_at=item.updated_at,
    )
    for item in response.items
  ]
  return ClaudeTodoMessageResponse(
    session_id=response.session_id,
    reply=response.reply,
    created_items=created_items,
    raw_payload=response.raw_payload,
  )
