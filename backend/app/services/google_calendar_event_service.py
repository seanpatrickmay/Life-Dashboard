"""Update Google Calendar events from UI actions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.google_calendar_client import GoogleCalendarClient, GoogleCalendarError
from app.db.models.calendar import CalendarEvent, GoogleCalendar
from app.services.google_calendar_connection_service import GoogleCalendarConnectionService
from app.services.google_calendar_sync_service import GoogleCalendarSyncService


class GoogleCalendarEventService:
    """Handles user-driven edits of Google Calendar events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.connection_service = GoogleCalendarConnectionService(session)
        self.sync_service = GoogleCalendarSyncService(session)

    async def update_event(
        self,
        event: CalendarEvent,
        calendar: GoogleCalendar,
        *,
        summary: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        scope: str = "occurrence",
        time_zone: str | None = None,
        is_all_day: bool | None = None,
    ) -> None:
        """Patch a Google Calendar event and refresh the local cache."""
        token = await self.connection_service.get_access_token(event.user_id)
        if not token:
            raise RuntimeError("Google Calendar connection missing or expired.")
        client = GoogleCalendarClient(token)
        all_day = event.is_all_day if is_all_day is None else is_all_day
        payload = _build_event_patch(
            summary,
            start_time,
            end_time,
            time_zone or calendar.time_zone,
            is_all_day=all_day,
        )

        try:
            if scope == "series" and event.recurring_event_id:
                await client.patch_event(calendar.google_id, event.recurring_event_id, payload)
                await self._refresh_calendar(calendar, start_time)
                return
            if scope == "future" and event.recurring_event_id:
                updated = await self._patch_future_occurrences(
                    client,
                    calendar,
                    event,
                    payload,
                    time_zone or calendar.time_zone,
                    is_all_day=all_day,
                )
                if updated:
                    await self._refresh_calendar(calendar, start_time)
                    return
            updated_event = await client.patch_event(
                calendar.google_id, event.google_event_id, payload
            )
        except GoogleCalendarError as exc:
            logger.warning("Failed to update Google Calendar event {}: {}", event.google_event_id, exc)
            raise

        await self.sync_service._upsert_event(event.user_id, calendar, updated_event)
        await self.session.commit()

    async def _patch_future_occurrences(
        self,
        client: GoogleCalendarClient,
        calendar: GoogleCalendar,
        event: CalendarEvent,
        payload: dict[str, Any],
        time_zone: str | None,
        is_all_day: bool,
    ) -> bool:
        master = await client.get_event(calendar.google_id, event.recurring_event_id or "")
        recurrence = master.get("recurrence") or []
        if not recurrence:
            return False
        if _recurrence_has_limit(recurrence):
            logger.info(
                "Recurring event has COUNT/UNTIL; applying full-series update instead of future split."
            )
            await client.patch_event(calendar.google_id, event.recurring_event_id or "", payload)
            return True

        occurrence_start = event.start_time
        if not occurrence_start:
            return False
        until = _format_rrule_until(occurrence_start)
        truncated_recurrence = [_replace_rrule_until(rule, until) for rule in recurrence]
        await client.patch_event(
            calendar.google_id,
            event.recurring_event_id or "",
            {"recurrence": truncated_recurrence},
        )

        new_recurrence = [_strip_rrule_limits(rule) for rule in recurrence]
        new_event_payload = {
            **master,
            **payload,
            "recurrence": new_recurrence,
        }
        new_event_payload.pop("id", None)
        new_event_payload.pop("etag", None)
        new_event_payload.pop("sequence", None)
        new_event_payload.pop("updated", None)
        new_event_payload.pop("recurringEventId", None)
        new_event_payload.pop("originalStartTime", None)
        if is_all_day:
            new_event_payload["start"] = payload.get("start") or _format_date_payload(
                event.start_time, time_zone
            )
            new_event_payload["end"] = payload.get("end") or _format_date_payload(
                event.end_time, time_zone
            )
        else:
            new_event_payload["start"] = payload.get("start") or _format_datetime_payload(
                event.start_time, time_zone
            )
            new_event_payload["end"] = payload.get("end") or _format_datetime_payload(
                event.end_time, time_zone
            )
        await client.insert_event(calendar.google_id, new_event_payload)
        return True

    async def _refresh_calendar(self, calendar: GoogleCalendar, start_time: datetime | None) -> None:
        now = datetime.now(timezone.utc)
        window_start = (start_time or now) - timedelta(days=7)
        window_end = (start_time or now) + timedelta(days=30)
        await self.sync_service.sync_events_for_calendar(
            calendar.user_id,
            calendar,
            window_start=window_start,
            window_end=window_end,
            force_full=False,
        )


def _build_event_patch(
    summary: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
    time_zone: str | None,
    *,
    is_all_day: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if summary is not None:
        payload["summary"] = summary
    if start_time is not None:
        payload["start"] = (
            _format_date_payload(start_time, time_zone)
            if is_all_day
            else _format_datetime_payload(start_time, time_zone)
        )
    if end_time is not None:
        payload["end"] = (
            _format_date_payload(end_time, time_zone)
            if is_all_day
            else _format_datetime_payload(end_time, time_zone)
        )
    return payload


def _format_datetime_payload(value: datetime | None, time_zone: str | None) -> dict[str, Any]:
    if value is None:
        return {"dateTime": None}
    tz_name = (time_zone or "UTC").strip() or "UTC"
    zone = ZoneInfo(tz_name)
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone)
    return {"dateTime": value.isoformat(), "timeZone": tz_name}


def _format_date_payload(value: datetime | None, time_zone: str | None) -> dict[str, Any]:
    if value is None:
        return {"date": None}
    tz_name = (time_zone or "UTC").strip() or "UTC"
    zone = ZoneInfo(tz_name)
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone)
    local_date = value.astimezone(zone).date()
    return {"date": local_date.isoformat()}


def _recurrence_has_limit(rules: list[str]) -> bool:
    for rule in rules:
        if "COUNT=" in rule or "UNTIL=" in rule:
            return True
    return False


def _format_rrule_until(occurrence_start: datetime) -> str:
    cutoff = occurrence_start - timedelta(seconds=1)
    cutoff_utc = cutoff.astimezone(timezone.utc)
    return cutoff_utc.strftime("%Y%m%dT%H%M%SZ")


def _replace_rrule_until(rule: str, until_value: str) -> str:
    if not rule.startswith("RRULE:"):
        return rule
    segments = rule.split(";")
    filtered = [seg for seg in segments if not seg.startswith("UNTIL=") and not seg.startswith("COUNT=")]
    filtered.append(f"UNTIL={until_value}")
    return ";".join(filtered)


def _strip_rrule_limits(rule: str) -> str:
    if not rule.startswith("RRULE:"):
        return rule
    segments = rule.split(";")
    filtered = [seg for seg in segments if not seg.startswith("UNTIL=") and not seg.startswith("COUNT=")]
    return ";".join(filtered)
