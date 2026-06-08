"""Pydantic schemas for the Morning Brief API."""
from __future__ import annotations

from pydantic import BaseModel


class ReadinessSignal(BaseModel):
    score: float | None = None
    label: str | None = None
    sleep_hours: float | None = None
    hrv_ms: float | None = None
    narrative: str | None = None


class EventSignal(BaseModel):
    summary: str | None = None
    start_time: str | None = None


class ReadSignal(BaseModel):
    title: str
    annotation: str | None = None


class MorningBriefRequest(BaseModel):
    readiness: ReadinessSignal | None = None
    events: list[EventSignal] = []
    overdue_tasks: list[str] = []
    reads: list[ReadSignal] = []


class MorningBriefResponse(BaseModel):
    paragraph: str
