"""Pydantic schemas for the AI Digest API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DigestItemResponse(BaseModel):
    id: int
    url: str
    title: str
    summary: str | None = None
    source_name: str
    category: str | None = None
    llm_summary: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class DigestResponse(BaseModel):
    items: list[DigestItemResponse]
    last_refreshed: datetime | None = None
    item_count: int
    is_stale: bool
    narrative: str | None = None


class RefreshResponse(BaseModel):
    started: bool
    message: str
