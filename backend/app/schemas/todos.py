from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TodoItemResponse(BaseModel):
  id: int
  text: str
  completed: bool
  deadline_utc: datetime | None = None
  deadline_is_date_only: bool = False
  is_overdue: bool
  created_at: datetime
  updated_at: datetime

  class Config:
    from_attributes = True


class TodoCreateRequest(BaseModel):
  text: str = Field(min_length=1, max_length=512)
  deadline_utc: datetime | None = None
  deadline_is_date_only: bool = False
  time_zone: str | None = Field(default=None, max_length=64)


class TodoUpdateRequest(BaseModel):
  text: str | None = Field(default=None, min_length=1, max_length=512)
  deadline_utc: datetime | None = Field(default=None)
  deadline_is_date_only: bool | None = Field(default=None)
  completed: bool | None = None
  time_zone: str | None = Field(default=None, max_length=64)


class ClaudeTodoMessageRequest(BaseModel):
  session_id: str | None = None
  message: str


class ClaudeTodoMessageResponse(BaseModel):
  session_id: str
  reply: str
  created_items: list[TodoItemResponse]
  raw_payload: dict[str, Any] | None = None
