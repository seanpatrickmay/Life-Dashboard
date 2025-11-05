from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel


class ActivitySummary(BaseModel):
    id: int
    name: str | None
    type: str | None
    start: datetime
    distance_km: float
    duration_min: float
    calories_kcal: float | None


class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    value: float | None


class DailyMetricResponse(BaseModel):
    date: date
    hrv_avg_ms: float | None
    rhr_bpm: float | None
    sleep_hours: float | None
    training_load: float | None
    training_volume_hours: float | None
    readiness_score: int | None
    readiness_label: str | None
    readiness_narrative: str | None


class MetricsOverviewResponse(BaseModel):
    generated_at: datetime
    range_label: str
    training_volume_hours: float
    training_volume_window_days: int
    training_load_avg: float | None
    training_load_trend: list[TimeSeriesPoint]
    hrv_trend_ms: list[TimeSeriesPoint]
    rhr_trend_bpm: list[TimeSeriesPoint]
    sleep_trend_hours: list[TimeSeriesPoint]
