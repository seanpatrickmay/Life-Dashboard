"""Batch operations for todos to reduce round trips."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.db.repositories.todo_repository import TodoRepository
from app.db.session import get_session
from app.db.models.entities import User
from app.services.todo_calendar_link_service import TodoCalendarLinkService
from app.services.async_ai_service import AsyncAIService
from app.utils.timezone import resolve_time_zone


router = APIRouter(prefix="/todos", tags=["todos"])


class BatchUpdateItem(BaseModel):
    id: int
    text: str | None = None
    completed: bool | None = None
    completed_at_utc: datetime | None = None
    deadline_utc: datetime | None = None
    deadline_is_date_only: bool | None = None
    time_horizon: str | None = None


class BatchUpdateRequest(BaseModel):
    updates: List[BatchUpdateItem] = Field(max_length=100)
    time_zone: str | None = None


class BatchUpdateResponse(BaseModel):
    success: bool
    updated_count: int


@router.patch("/batch", response_model=BatchUpdateResponse)
async def batch_update_todos(
    payload: BatchUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BatchUpdateResponse:
    """Update multiple todos in a single request."""
    repo = TodoRepository(session)
    link_service = TodoCalendarLinkService(session)
    updated_count = 0

    for update_item in payload.updates:
        todo = await repo.get_for_user(current_user.id, update_item.id)
        if not todo:
            continue

        # Apply updates
        if update_item.text is not None:
            todo.text = update_item.text.strip()

        if update_item.deadline_utc is not None:
            todo.deadline_utc = update_item.deadline_utc

        if update_item.deadline_is_date_only is not None:
            todo.deadline_is_date_only = update_item.deadline_is_date_only

        if update_item.time_horizon is not None:
            todo.time_horizon = update_item.time_horizon

        if update_item.completed is not None:
            todo.mark_completed(update_item.completed, completed_at_utc=update_item.completed_at_utc)
            if update_item.completed:
                tz_name = (payload.time_zone or todo.completed_time_zone or "UTC").strip() or "UTC"
                todo.completed_time_zone = tz_name
                if todo.completed_at_utc:
                    zone = resolve_time_zone(tz_name)
                    todo.completed_local_date = todo.completed_at_utc.astimezone(zone).date()
                if not todo.accomplishment_text:
                    cached_accomplishment = AsyncAIService.get_cached_accomplishment(todo.text)
                    if cached_accomplishment:
                        todo.accomplishment_text = cached_accomplishment
                        todo.accomplishment_generated_at_utc = datetime.now(timezone.utc)
                    else:
                        todo.accomplishment_text = f"Completed {todo.text}".strip()
                        AsyncAIService.schedule_accomplishment_generation(todo.id, current_user.id, todo.text)

        await session.flush()

        # Calendar link sync (mirrors single-update endpoint logic)
        if update_item.completed is not None or update_item.deadline_utc is not None:
            if todo.completed:
                await link_service.unlink_todo(todo, delete_event=True)
            elif todo.deadline_utc is not None:
                await link_service.upsert_event_for_todo(todo, time_zone=payload.time_zone)
            else:
                await link_service.unlink_todo(todo, delete_event=True)

        updated_count += 1

    await session.commit()

    return BatchUpdateResponse(success=True, updated_count=updated_count)
