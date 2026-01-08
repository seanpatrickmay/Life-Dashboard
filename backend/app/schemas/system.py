from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RefreshStatusResponse(BaseModel):
    job_started: bool
    running: bool
    last_started_at: datetime | None = None
    last_completed_at: datetime | None = None
    next_allowed_at: datetime | None = None
    cooldown_seconds: int
    message: str | None = None
    last_error: str | None = None
