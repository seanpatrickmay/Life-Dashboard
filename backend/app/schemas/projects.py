from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.todos import TodoItemResponse


class ProjectResponse(BaseModel):
  id: int
  name: str
  display_name: str | None = None
  notes: str | None = None
  archived: bool
  sort_order: int
  created_at: datetime
  updated_at: datetime
  open_count: int = 0
  completed_count: int = 0
  state_summary_json: dict | None = None
  state_updated_at_utc: datetime | None = None

  class Config:
    from_attributes = True


class ProjectActivityResponse(BaseModel):
  id: int
  project_id: int
  project_name: str | None = None
  local_date: date
  session_id: str
  summary: str
  details_json: dict | None = None
  created_at: datetime

  class Config:
    from_attributes = True


class ProjectSuggestionResponse(BaseModel):
  todo_id: int
  suggested_project_name: str
  confidence: float
  reason: str | None = None


class ProjectBoardResponse(BaseModel):
  projects: list[ProjectResponse]
  todos: list[TodoItemResponse]
  suggestions: list[ProjectSuggestionResponse]


class ProjectCreateRequest(BaseModel):
  name: str = Field(min_length=1, max_length=255)
  notes: str | None = None
  sort_order: int = 0


class ProjectUpdateRequest(BaseModel):
  name: str | None = Field(default=None, min_length=1, max_length=255)
  display_name: str | None = Field(default=None, max_length=255)
  notes: str | None = None
  archived: bool | None = None
  sort_order: int | None = None


class SuggestionRecomputeRequest(BaseModel):
  scope: str = Field(default="inbox")
  todo_ids: list[int] | None = None
