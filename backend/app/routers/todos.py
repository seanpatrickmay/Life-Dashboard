from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.todo_repository import TodoRepository
from app.db.session import get_session
from app.schemas.todos import (
  ClaudeTodoMessageRequest,
  ClaudeTodoMessageResponse,
  TodoCreateRequest,
  TodoItemResponse,
  TodoUpdateRequest,
)
from app.services.claude_todo_agent import ClaudeTodoAgent


router = APIRouter(prefix="/todos", tags=["todos"])

DEFAULT_USER_ID = 1


@router.get("", response_model=list[TodoItemResponse])
async def list_todos(session: AsyncSession = Depends(get_session)) -> list[TodoItemResponse]:
  repo = TodoRepository(session)
  items = await repo.list_for_user(DEFAULT_USER_ID)
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
  payload: TodoCreateRequest, session: AsyncSession = Depends(get_session)
) -> TodoItemResponse:
  repo = TodoRepository(session)
  todo = await repo.create_one(DEFAULT_USER_ID, payload.text, payload.deadline_utc)
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
  session: AsyncSession = Depends(get_session),
) -> TodoItemResponse:
  repo = TodoRepository(session)
  todo = await repo.get_for_user(DEFAULT_USER_ID, todo_id)
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
    todo.mark_completed(update_data["completed"])
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
async def delete_todo(todo_id: int, session: AsyncSession = Depends(get_session)) -> Response:
  repo = TodoRepository(session)
  todo = await repo.get_for_user(DEFAULT_USER_ID, todo_id)
  if todo is None:
    raise HTTPException(status_code=404, detail="Todo not found")
  await session.delete(todo)
  await session.commit()
  return Response(status_code=204)


@router.post("/claude/message", response_model=ClaudeTodoMessageResponse)
async def claude_todo_message(
  payload: ClaudeTodoMessageRequest, session: AsyncSession = Depends(get_session)
) -> ClaudeTodoMessageResponse:
  agent = ClaudeTodoAgent(session)
  response = await agent.respond(DEFAULT_USER_ID, payload.message, payload.session_id)
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
