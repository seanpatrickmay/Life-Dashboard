from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class InsightResponse(BaseModel):
    metric_date: datetime
    readiness_score: int | None
    readiness_label: str | None
    narrative: str
    source_model: str
    last_updated: datetime
    refreshing: bool = False
