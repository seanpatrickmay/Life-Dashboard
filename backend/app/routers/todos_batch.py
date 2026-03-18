"""Batch operations for todos to reduce round trips."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.db.repositories.todo_repository import TodoRepository
from app.db.session import get_session
from app.db.models.entities import User


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
    updates: List[BatchUpdateItem]
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
    updated_count = 0

    for update_item in payload.updates:
        todo = await repo.get_for_user(current_user.id, update_item.id)
        if not todo:
            continue

        # Apply updates
        if update_item.text is not None:
            todo.text = update_item.text.strip()

        if update_item.completed is not None:
            todo.mark_completed(update_item.completed, completed_at_utc=update_item.completed_at_utc)

        if update_item.deadline_utc is not None:
            todo.deadline_utc = update_item.deadline_utc

        if update_item.deadline_is_date_only is not None:
            todo.deadline_is_date_only = update_item.deadline_is_date_only

        if update_item.time_horizon is not None:
            todo.time_horizon = update_item.time_horizon

        updated_count += 1

    await session.commit()

    return BatchUpdateResponse(success=True, updated_count=updated_count)