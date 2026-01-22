from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CalendarStatusResponse(BaseModel):
    connected: bool
    account_email: str | None
    connected_at: datetime | None
    last_sync_at: datetime | None
    requires_reauth: bool


class CalendarSummary(BaseModel):
    google_id: str
    summary: str
    selected: bool
    primary: bool
    is_life_dashboard: bool
    color_id: str | None = None
    time_zone: str | None = None


class CalendarListResponse(BaseModel):
    calendars: list[CalendarSummary]


class CalendarSelectionRequest(BaseModel):
    google_ids: list[str] = Field(default_factory=list)


class CalendarEventResponse(BaseModel):
    id: int
    calendar_google_id: str
    calendar_summary: str
    calendar_primary: bool
    calendar_is_life_dashboard: bool
    google_event_id: str
    recurring_event_id: str | None
    ical_uid: str | None
    summary: str | None
    description: str | None
    location: str | None
    start_time: datetime | None
    end_time: datetime | None
    is_all_day: bool
    status: str | None
    visibility: str | None
    transparency: str | None
    hangout_link: str | None
    conference_link: str | None
    organizer: dict[str, Any] | None
    attendees: list[Any] | None


class CalendarEventsResponse(BaseModel):
    events: list[CalendarEventResponse]


class CalendarEventUpdateRequest(BaseModel):
    summary: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_all_day: bool | None = None
    scope: str = Field(default="occurrence", pattern="^(occurrence|future|series)$")
