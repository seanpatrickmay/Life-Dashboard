from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkspacePageSummary(BaseModel):
    id: int
    parent_page_id: int | None = None
    title: str
    kind: str
    icon: str | None = None
    cover_url: str | None = None
    description: str | None = None
    show_in_sidebar: bool
    sort_order: int
    is_home: bool
    trashed_at: datetime | None = None
    legacy_project_id: int | None = None
    legacy_todo_id: int | None = None
    legacy_note_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkspacePropertyOptionResponse(BaseModel):
    id: int
    label: str
    value: str
    color: str | None = None
    sort_order: int

    class Config:
        from_attributes = True


class WorkspacePropertyResponse(BaseModel):
    id: int
    name: str
    slug: str
    property_type: str
    sort_order: int
    required: bool
    config_json: dict | list | None = None
    options: list[WorkspacePropertyOptionResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkspacePropertyValueResponse(BaseModel):
    property_id: int
    property_slug: str
    property_name: str
    property_type: str
    value: Any = None


class WorkspaceViewResponse(BaseModel):
    id: int
    name: str
    view_type: str
    sort_order: int
    is_default: bool
    config_json: dict | list | None = None

    class Config:
        from_attributes = True


class WorkspacePageLinkResponse(BaseModel):
    id: int
    title: str
    kind: str
    icon: str | None = None


class WorkspaceBlockResponse(BaseModel):
    id: int
    page_id: int
    parent_block_id: int | None = None
    block_type: str
    sort_order: int
    text_content: str
    checked: bool
    data_json: dict | list | None = None
    links: list[WorkspacePageLinkResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkspaceDatabaseSummary(BaseModel):
    id: int
    page_id: int
    name: str
    description: str | None = None
    icon: str | None = None
    is_seeded: bool
    properties: list[WorkspacePropertyResponse] = Field(default_factory=list)
    views: list[WorkspaceViewResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkspaceRowResponse(BaseModel):
    page: WorkspacePageSummary
    properties: list[WorkspacePropertyValueResponse] = Field(default_factory=list)


class WorkspaceBacklinkResponse(BaseModel):
    source_page: WorkspacePageLinkResponse
    block_id: int | None = None
    snippet: str | None = None


class WorkspaceBacklinksResponse(BaseModel):
    backlinks: list[WorkspaceBacklinkResponse] = Field(default_factory=list)


class WorkspacePageDetailResponse(BaseModel):
    page: WorkspacePageSummary
    breadcrumbs: list[WorkspacePageSummary] = Field(default_factory=list)
    children: list[WorkspacePageSummary] = Field(default_factory=list)
    properties: list[WorkspacePropertyValueResponse] = Field(default_factory=list)
    blocks: list[WorkspaceBlockResponse] = Field(default_factory=list)
    database: WorkspaceDatabaseSummary | None = None
    linked_databases: list[WorkspaceDatabaseSummary] = Field(default_factory=list)
    favorite: bool = False


class WorkspaceBootstrapResponse(BaseModel):
    home_page_id: int
    read_only: bool = False
    sidebar_pages: list[WorkspacePageSummary] = Field(default_factory=list)
    favorites: list[WorkspacePageSummary] = Field(default_factory=list)
    recent_pages: list[WorkspacePageSummary] = Field(default_factory=list)
    trash_pages: list[WorkspacePageSummary] = Field(default_factory=list)
    databases: list[WorkspaceDatabaseSummary] = Field(default_factory=list)


class WorkspaceSearchResult(BaseModel):
    page: WorkspacePageSummary
    match: str | None = None


class WorkspaceSearchResponse(BaseModel):
    results: list[WorkspaceSearchResult] = Field(default_factory=list)


class WorkspaceTemplateResponse(BaseModel):
    id: int
    database_id: int | None = None
    name: str
    title: str | None = None
    icon: str | None = None
    cover_url: str | None = None
    sort_order: int

    class Config:
        from_attributes = True


class WorkspaceDatabaseRowsResponse(BaseModel):
    database: WorkspaceDatabaseSummary
    view: WorkspaceViewResponse | None = None
    rows: list[WorkspaceRowResponse] = Field(default_factory=list)
    total_count: int = 0
    offset: int = 0
    limit: int = 50
    has_more: bool = False


class WorkspaceCreatePageRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    parent_page_id: int | None = None
    kind: str = "page"
    icon: str | None = Field(default=None, max_length=64)
    cover_url: str | None = None
    description: str | None = None
    show_in_sidebar: bool = True
    template_id: int | None = None
    database_page_id: int | None = None
    sort_order: int | None = None
    extra_json: dict | list | None = None


class WorkspaceUpdatePageRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    icon: str | None = Field(default=None, max_length=64)
    cover_url: str | None = None
    description: str | None = None
    parent_page_id: int | None = None
    show_in_sidebar: bool | None = None
    sort_order: int | None = None
    favorite: bool | None = None
    trashed: bool | None = None


class WorkspaceCreateBlockRequest(BaseModel):
    page_id: int
    after_block_id: int | None = None
    block_type: str = "paragraph"
    text_content: str = ""
    checked: bool = False
    data_json: dict | list | None = None


class WorkspaceUpdateBlockRequest(BaseModel):
    block_type: str | None = None
    text_content: str | None = None
    checked: bool | None = None
    data_json: dict | list | None = None


class WorkspaceReorderBlocksRequest(BaseModel):
    page_id: int
    ordered_block_ids: list[int]


class WorkspaceUpdatePropertyValuesRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class WorkspaceCreateRowRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    properties: dict[str, Any] = Field(default_factory=dict)
    template_id: int | None = None


class WorkspaceCreateViewRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    view_type: str = Field(min_length=1, max_length=32)
    is_default: bool = False
    config_json: dict | list | None = None


class WorkspaceUpdateViewRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_default: bool | None = None
    config_json: dict | list | None = None


class WorkspaceApplyTemplateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    properties: dict[str, Any] = Field(default_factory=dict)


class WorkspaceAssetCreateRequest(BaseModel):
    page_id: int | None = None
    block_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=128)
    size_bytes: int | None = None


class WorkspaceAssetUploadResponse(BaseModel):
    asset_id: int
    upload_url: str
    public_url: str
    headers: dict[str, str] = Field(default_factory=dict)
    status: str
