from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.todos import TodoItemResponse


class MonetMessageRequest(BaseModel):
    """Chat payload for the Monet assistant."""

    message: str = Field(min_length=1)
    session_id: str | None = None
    window_days: int = Field(default=14, ge=1, le=30)
    time_zone: str | None = None


class MonetMessageResponse(BaseModel):
    """Assistant reply plus structured tool outcomes."""

    session_id: str
    reply: str
    nutrition_entries: list[dict[str, Any]]
    todo_items: list[TodoItemResponse]
    tools_used: list[str]
