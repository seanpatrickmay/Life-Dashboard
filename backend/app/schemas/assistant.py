from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.todos import TodoItemResponse


class AssistantVisibleRange(BaseModel):
    start_iso: str
    end_iso: str


class AssistantSelectedEntity(BaseModel):
    project_id: int | None = None
    project_name: str | None = None
    note_id: int | None = None
    note_title: str | None = None
    calendar_event_id: int | None = None
    todo_id: int | None = None
    recurrence_scope: Literal["occurrence", "future", "series"] | None = None


class AssistantPageContext(BaseModel):
    page: Literal["calendar", "projects"]
    selected_entity: AssistantSelectedEntity | None = None
    visible_range: AssistantVisibleRange | None = None


class AssistantAction(BaseModel):
    action_type: Literal[
        "calendar.create_event",
        "calendar.update_event",
        "projects.create_todo",
        "projects.create_note",
        "projects.update_note",
    ]
    params: dict[str, Any] = Field(default_factory=dict)


class MonetMessageRequest(BaseModel):
    """Chat payload for the Monet assistant."""

    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    window_days: int = Field(default=7, ge=1, le=30)
    time_zone: str | None = None
    page_context: AssistantPageContext | None = None
    execution_mode: Literal["auto", "preview", "commit"] = "auto"
    proposed_actions: list[AssistantAction] = Field(default_factory=list)


class MonetMessageResponse(BaseModel):
    """Assistant reply plus structured tool outcomes."""

    session_id: str
    reply: str
    nutrition_entries: list[dict[str, Any]]
    todo_items: list[TodoItemResponse]
    tools_used: list[str]
    requires_confirmation: bool = False
    proposed_actions: list[AssistantAction] = Field(default_factory=list)
    action_plan_id: str | None = None
