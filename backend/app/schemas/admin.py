from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class IngestionTriggerResponse(BaseModel):
    started_at: datetime
    status: str
    message: str
