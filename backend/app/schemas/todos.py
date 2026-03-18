from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TodoItemResponse(BaseModel):
  id: int
  project_id: int
  text: str
  completed: bool
  completed_at_utc: datetime | None = None
  deadline_utc: datetime | None = None
  deadline_is_date_only: bool = False
  time_horizon: str = "this_week"
  is_overdue: bool
  created_at: datetime
  updated_at: datetime

  class Config:
    from_attributes = True


class TodoCreateRequest(BaseModel):
  text: str = Field(min_length=1, max_length=512)
  project_id: int | None = None
  deadline_utc: datetime | None = None
  deadline_is_date_only: bool = False
  time_horizon: str = "this_week"
  time_zone: str | None = Field(default=None, max_length=64)


class TodoUpdateRequest(BaseModel):
  text: str | None = Field(default=None, min_length=1, max_length=512)
  project_id: int | None = Field(default=None)
  deadline_utc: datetime | None = Field(default=None)
  deadline_is_date_only: bool | None = Field(default=None)
  time_horizon: str | None = Field(default=None)
  completed: bool | None = None
  completed_at_utc: datetime | None = None
  time_zone: str | None = Field(default=None, max_length=64)


class TodoAssistantMessageRequest(BaseModel):
  session_id: str | None = None
  message: str


class TodoAssistantMessageResponse(BaseModel):
  session_id: str
  reply: str
  created_items: list[TodoItemResponse]
  raw_payload: dict[str, Any] | None = None


ClaudeTodoMessageRequest = TodoAssistantMessageRequest
ClaudeTodoMessageResponse = TodoAssistantMessageResponse
