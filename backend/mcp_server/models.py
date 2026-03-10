from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.workspace import (
    WorkspaceCreateBlockRequest,
    WorkspaceCreatePageRequest,
    WorkspaceCreateRowRequest,
    WorkspaceUpdateBlockRequest,
    WorkspaceUpdatePageRequest,
    WorkspaceUpdatePropertyValuesRequest,
)


class ProjectUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None
    favorite: bool | None = None
    trashed: bool | None = None


class TaskUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None
    due: str | None = None
    date_only: bool | None = None
    project_id: int | None = None


class WorkspaceCreatePageInput(WorkspaceCreatePageRequest):
    pass


class WorkspaceUpdatePageInput(WorkspaceUpdatePageRequest):
    pass


class WorkspaceCreateBlockInput(WorkspaceCreateBlockRequest):
    pass


class WorkspaceUpdateBlockInput(WorkspaceUpdateBlockRequest):
    pass


class WorkspaceCreateDatabaseRowInput(WorkspaceCreateRowRequest):
    pass


class WorkspaceUpdatePropertiesInput(WorkspaceUpdatePropertyValuesRequest):
    values: dict[str, Any] = Field(default_factory=dict)
