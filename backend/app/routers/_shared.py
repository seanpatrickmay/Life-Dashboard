"""Shared helpers used across multiple router modules."""
from __future__ import annotations

from datetime import datetime

from app.db.models.todo import TodoItem
from app.db.session import AsyncSessionLocal
from app.schemas.todos import TodoItemResponse
from app.services.todo_project_suggestion_service import TodoProjectSuggestionService


def build_todo_response(item: TodoItem, now_utc: datetime) -> TodoItemResponse:
    """Build a TodoItemResponse from a TodoItem, including all fields."""
    return TodoItemResponse(
        id=item.id,
        project_id=item.project_id,
        text=item.text,
        completed=item.completed,
        completed_at_utc=item.completed_at_utc,
        deadline_utc=item.deadline_utc,
        deadline_is_date_only=item.deadline_is_date_only,
        time_horizon=item.time_horizon or "this_week",
        is_overdue=bool(
            not item.completed and item.deadline_utc is not None and item.deadline_utc < now_utc
        ),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def run_project_suggestions(user_id: int, todo_ids: list[int]) -> None:
    """Run project suggestion inference for the given todo IDs."""
    if not todo_ids:
        return
    async with AsyncSessionLocal() as session:
        service = TodoProjectSuggestionService(session)
        await service.process_todo_ids(user_id=user_id, todo_ids=todo_ids)
