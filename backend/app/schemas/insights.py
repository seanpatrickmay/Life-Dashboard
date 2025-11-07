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
    greeting: str | None = None
    hrv_value_ms: float | None = None
    hrv_note: str | None = None
    hrv_score: float | None = None
    rhr_value_bpm: float | None = None
    rhr_note: str | None = None
    rhr_score: float | None = None
    sleep_value_hours: float | None = None
    sleep_note: str | None = None
    sleep_score: float | None = None
    training_load_value: float | None = None
    training_load_note: str | None = None
    training_load_score: float | None = None
    morning_note: str | None = None
