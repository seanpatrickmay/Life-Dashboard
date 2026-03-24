"""Shared calendar helper utilities."""
from __future__ import annotations

from typing import Any

from app.db.models.calendar import CalendarEvent, GoogleCalendar, TodoEventLink
from app.schemas.calendar import CalendarEventResponse


def is_declined_attendee(attendees: list[dict[str, object]] | None) -> bool:
    """Return True if the authenticated user has declined the event."""
    if not attendees:
        return False
    for attendee in attendees:
        if attendee.get("self") and attendee.get("responseStatus") == "declined":
            return True
    return False


def is_declined_event(payload: dict[str, Any]) -> bool:
    """Return True if the event payload indicates the user declined."""
    return is_declined_attendee(payload.get("attendees") or [])


def build_calendar_event_response(
    event: CalendarEvent,
    calendar: GoogleCalendar,
    link: TodoEventLink | None = None,
) -> CalendarEventResponse:
    """Construct a CalendarEventResponse from ORM models."""
    return CalendarEventResponse(
        id=event.id,
        todo_id=link.todo_id if link else None,
        calendar_google_id=calendar.google_id,
        calendar_summary=calendar.summary,
        calendar_primary=calendar.primary,
        calendar_is_life_dashboard=calendar.is_life_dashboard,
        google_event_id=event.google_event_id,
        recurring_event_id=event.recurring_event_id,
        ical_uid=event.ical_uid,
        summary=event.summary,
        description=event.description,
        location=event.location,
        start_time=event.start_time,
        end_time=event.end_time,
        is_all_day=event.is_all_day,
        status=event.status,
        visibility=event.visibility,
        transparency=event.transparency,
        hangout_link=event.hangout_link,
        conference_link=event.conference_link,
        organizer=event.organizer,
        attendees=event.attendees,
    )
