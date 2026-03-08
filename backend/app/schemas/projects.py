from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.todos import TodoItemResponse


class ProjectResponse(BaseModel):
  id: int
  name: str
  notes: str | None = None
  archived: bool
  sort_order: int
  created_at: datetime
  updated_at: datetime
  open_count: int = 0
  completed_count: int = 0

  class Config:
    from_attributes = True


class ProjectSuggestionResponse(BaseModel):
  todo_id: int
  suggested_project_name: str
  confidence: float
  reason: str | None = None


class ProjectNoteResponse(BaseModel):
  id: int
  user_id: int
  project_id: int
  title: str
  body_markdown: str
  tags: list[str]
  archived: bool
  pinned: bool
  created_at: datetime
  updated_at: datetime

  class Config:
    from_attributes = True


class ProjectNoteCreateRequest(BaseModel):
  title: str = Field(min_length=1, max_length=255)
  body_markdown: str = ""
  tags: list[str] = Field(default_factory=list)
  pinned: bool = False


class ProjectNoteUpdateRequest(BaseModel):
  title: str | None = Field(default=None, min_length=1, max_length=255)
  body_markdown: str | None = None
  tags: list[str] | None = None
  archived: bool | None = None
  pinned: bool | None = None


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
  notes: str | None = None
  archived: bool | None = None
  sort_order: int | None = None


class SuggestionRecomputeRequest(BaseModel):
  scope: str = Field(default="inbox")
  todo_ids: list[int] | None = None
