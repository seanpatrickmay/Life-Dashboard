"""Google Calendar sync orchestration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser
from urllib.parse import urlparse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.google_calendar_client import GoogleCalendarClient, GoogleCalendarError
from app.core.config import settings
from app.db.models.calendar import CalendarEvent, GoogleCalendar, GoogleCalendarConnection
from app.services.google_calendar_connection_service import GoogleCalendarConnectionService
from app.services.google_calendar_constants import LIFE_DASHBOARD_CALENDAR_NAME
from app.services.todo_calendar_link_service import TodoCalendarLinkService


class GoogleCalendarSyncService:
    """Syncs calendars and events to the local database cache."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.connection_service = GoogleCalendarConnectionService(session)
        self.todo_link_service = TodoCalendarLinkService(session)

    async def sync_calendars(self, user_id: int) -> list[GoogleCalendar]:
        """Fetch the user's calendar list from Google and upsert locally."""
        connection = await self._require_connection(user_id)
        token = await self.connection_service.get_access_token(user_id)
        if not token:
            raise RuntimeError("Google Calendar connection missing or expired.")
        client = GoogleCalendarClient(token)
        items = await client.list_calendars()
        calendars: list[GoogleCalendar] = []
        for item in items:
            calendar = await self._upsert_calendar(user_id, connection, item)
            calendars.append(calendar)
        await self.session.commit()
        return calendars

    async def ensure_life_dashboard_calendar(self, user_id: int) -> GoogleCalendar:
        """Ensure the Life Dashboard calendar exists and is selected."""
        connection = await self._require_connection(user_id)
        token = await self.connection_service.get_access_token(user_id)
        if not token:
            raise RuntimeError("Google Calendar connection missing or expired.")
        client = GoogleCalendarClient(token)

        existing = await self._get_calendar_by_name(user_id, LIFE_DASHBOARD_CALENDAR_NAME)
        if existing:
            existing.selected = True
            existing.is_life_dashboard = True
            await self.session.commit()
            return existing

        created = await client.create_calendar(
            summary=LIFE_DASHBOARD_CALENDAR_NAME,
            description="Life Dashboard todos and planning",
        )
        calendar = await self._upsert_calendar(user_id, connection, created)
        calendar.selected = True
        calendar.is_life_dashboard = True
        await self.session.commit()
        return calendar

    async def sync_selected_events(
        self,
        user_id: int,
        *,
        window_start: datetime,
        window_end: datetime,
        force_full: bool = False,
    ) -> None:
        """Sync events for all selected calendars in the provided window."""
        calendars = await self._list_selected_calendars(user_id)
        for calendar in calendars:
            await self.sync_events_for_calendar(
                user_id,
                calendar,
                window_start=window_start,
                window_end=window_end,
                force_full=force_full,
            )
            await self.ensure_watch(calendar)

    async def sync_events_for_calendar(
        self,
        user_id: int,
        calendar: GoogleCalendar,
        *,
        window_start: datetime,
        window_end: datetime,
        force_full: bool = False,
    ) -> None:
        """Sync events for a single calendar."""
        token = await self.connection_service.get_access_token(user_id)
        if not token:
            raise RuntimeError("Google Calendar connection missing or expired.")
        client = GoogleCalendarClient(token)
        sync_token = None if force_full else calendar.sync_token

        try:
            payload = await client.list_events(
                calendar.google_id,
                time_min=window_start.isoformat(),
                time_max=window_end.isoformat(),
                sync_token=sync_token,
            )
        except GoogleCalendarError as exc:
            if exc.status_code == 410:
                logger.info("Google Calendar sync token invalid; full resync for {}", calendar.google_id)
                calendar.sync_token = None
                await self.session.commit()
                payload = await client.list_events(
                    calendar.google_id,
                    time_min=window_start.isoformat(),
                    time_max=window_end.isoformat(),
                )
            elif exc.status_code in {403, 404}:
                logger.warning(
                    "Skipping calendar {} during sync (status {}).",
                    calendar.google_id,
                    exc.status_code,
                )
                return
            else:
                raise

        items = payload.get("items", [])
        for item in items:
            status = item.get("status")
            if status == "cancelled":
                await self._delete_event(calendar.id, item.get("id"))
                await self.todo_link_service.handle_event_deleted(calendar.id, item.get("id"))
                continue
            if _is_declined_event(item):
                await self._delete_event(calendar.id, item.get("id"))
                continue
            await self._upsert_event(user_id, calendar, item)

        sync_token = payload.get("nextSyncToken")
        if sync_token:
            calendar.sync_token = sync_token
        now = datetime.now(timezone.utc)
        calendar.last_synced_at = now
        connection = await self.connection_service.get_connection(user_id)
        if connection:
            connection.last_sync_at = now
        await self.session.commit()

    async def ensure_watch(self, calendar: GoogleCalendar) -> None:
        """Ensure the Google webhook channel is registered and not expiring."""
        webhook_url = settings.google_calendar_webhook_url
        parsed = urlparse(webhook_url)
        if parsed.scheme != "https":
            logger.info(
                "Skipping Google Calendar watch; webhook must be HTTPS (got {}).",
                webhook_url,
            )
            return
        if calendar.channel_expiration and calendar.channel_expiration > datetime.now(timezone.utc) + timedelta(
            hours=6
        ):
            return
        token = await self.connection_service.get_access_token(calendar.user_id)
        if not token:
            raise RuntimeError("Google Calendar connection missing or expired.")
        client = GoogleCalendarClient(token)
        channel_id = f"ld-{calendar.user_id}-{uuid4()}"
        try:
            response = await client.watch_events(
                calendar.google_id,
                channel_id=channel_id,
                address=settings.google_calendar_webhook_url,
            )
        except GoogleCalendarError as exc:
            logger.warning(
                "Failed to register Google Calendar watch for {}: {}", calendar.google_id, exc
            )
            return
        calendar.channel_id = response.get("id")
        calendar.channel_resource_id = response.get("resourceId")
        expiration = response.get("expiration")
        if expiration:
            try:
                calendar.channel_expiration = datetime.fromtimestamp(int(expiration) / 1000, tz=timezone.utc)
            except Exception:
                calendar.channel_expiration = None
        await self.session.commit()

    async def _get_calendar_by_name(self, user_id: int, name: str) -> GoogleCalendar | None:
        stmt = select(GoogleCalendar).where(
            GoogleCalendar.user_id == user_id, GoogleCalendar.summary == name
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _list_selected_calendars(self, user_id: int) -> list[GoogleCalendar]:
        stmt = (
            select(GoogleCalendar)
            .where(GoogleCalendar.user_id == user_id, GoogleCalendar.selected.is_(True))
            .order_by(GoogleCalendar.is_life_dashboard.desc(), GoogleCalendar.primary.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _upsert_calendar(
        self, user_id: int, connection: GoogleCalendarConnection, payload: dict[str, Any]
    ) -> GoogleCalendar:
        google_id = payload.get("id")
        if not google_id:
            raise ValueError("Google Calendar id missing.")
        display_name = payload.get("summaryOverride") or payload.get("summary") or "Untitled"
        stmt = select(GoogleCalendar).where(
            GoogleCalendar.user_id == user_id, GoogleCalendar.google_id == google_id
        )
        result = await self.session.execute(stmt)
        calendar = result.scalar_one_or_none()
        if calendar is None:
            calendar = GoogleCalendar(
                user_id=user_id,
                connection_id=connection.id,
                google_id=google_id,
                summary=display_name,
                description=payload.get("description"),
                time_zone=payload.get("timeZone"),
                access_role=payload.get("accessRole"),
                primary=bool(payload.get("primary")),
                selected=bool(payload.get("primary")),
                is_life_dashboard=payload.get("summary") == LIFE_DASHBOARD_CALENDAR_NAME,
                color_id=payload.get("colorId"),
            )
            self.session.add(calendar)
        else:
            calendar.connection_id = connection.id
            calendar.summary = display_name or calendar.summary
            calendar.description = payload.get("description")
            calendar.time_zone = payload.get("timeZone")
            calendar.access_role = payload.get("accessRole")
            calendar.primary = bool(payload.get("primary"))
            calendar.color_id = payload.get("colorId")
            if payload.get("summary") == LIFE_DASHBOARD_CALENDAR_NAME:
                calendar.is_life_dashboard = True
        return calendar

    async def _upsert_event(
        self, user_id: int, calendar: GoogleCalendar, payload: dict[str, Any]
    ) -> CalendarEvent:
        event_id = payload.get("id")
        if not event_id:
            raise ValueError("Event id missing from Google payload.")
        stmt = select(CalendarEvent).where(
            CalendarEvent.calendar_id == calendar.id, CalendarEvent.google_event_id == event_id
        )
        result = await self.session.execute(stmt)
        event = result.scalar_one_or_none()
        if event is None:
            event = CalendarEvent(
                user_id=user_id,
                calendar_id=calendar.id,
                google_event_id=event_id,
            )
            self.session.add(event)

        start_time, end_time, is_all_day = _parse_event_times(
            payload.get("start"),
            payload.get("end"),
            calendar.time_zone,
        )
        event.recurring_event_id = payload.get("recurringEventId")
        event.ical_uid = payload.get("iCalUID")
        event.summary = payload.get("summary")
        event.description = payload.get("description")
        event.location = payload.get("location")
        event.start_time = start_time
        event.end_time = end_time
        event.is_all_day = is_all_day
        event.status = payload.get("status")
        event.visibility = payload.get("visibility")
        event.transparency = payload.get("transparency")
        event.updated_at_google = _parse_google_datetime(payload.get("updated"))
        event.html_link = payload.get("htmlLink")
        event.hangout_link = payload.get("hangoutLink")
        event.conference_link = _extract_conference_link(payload)
        event.organizer = payload.get("organizer")
        event.attendees = payload.get("attendees")
        event.raw_payload = payload
        await self.todo_link_service.handle_event_updated(
            calendar.id,
            event_id,
            event_payload=payload,
            event_updated_at=event.updated_at_google,
            start_time=start_time,
            end_time=end_time,
            time_zone=calendar.time_zone,
        )
        return event

    async def _delete_event(self, calendar_id: int, google_event_id: str | None) -> None:
        if not google_event_id:
            return
        stmt = select(CalendarEvent).where(
            CalendarEvent.calendar_id == calendar_id,
            CalendarEvent.google_event_id == google_event_id,
        )
        result = await self.session.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            await self.session.delete(event)

    async def _require_connection(self, user_id: int) -> GoogleCalendarConnection:
        connection = await self.connection_service.get_connection(user_id)
        if not connection:
            raise RuntimeError("Google Calendar connection not found.")
        return connection


def _parse_event_times(
    start: dict[str, Any] | None, end: dict[str, Any] | None, calendar_tz: str | None
) -> tuple[datetime | None, datetime | None, bool]:
    if not start or not end:
        return None, None, False
    tz_name = (calendar_tz or "UTC").strip() or "UTC"
    zone = ZoneInfo(tz_name)
    if "dateTime" in start:
        start_dt = date_parser.isoparse(start["dateTime"])
        end_dt = date_parser.isoparse(end.get("dateTime")) if end.get("dateTime") else None
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=zone)
        if end_dt and end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=zone)
        return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc) if end_dt else None, False
    if "date" in start:
        start_date = date_parser.isoparse(start["date"]).date()
        end_date = date_parser.isoparse(end["date"]).date() if end.get("date") else start_date
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=zone)
        end_dt = datetime.combine(end_date, datetime.min.time(), tzinfo=zone)
        return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc), True
    return None, None, False


def _parse_google_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = date_parser.isoparse(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _extract_conference_link(payload: dict[str, Any]) -> str | None:
    conference = payload.get("conferenceData") or {}
    entry_points = conference.get("entryPoints") or []
    for entry in entry_points:
        uri = entry.get("uri")
        if uri:
            return uri
    return None


def _is_declined_event(payload: dict[str, Any]) -> bool:
    attendees = payload.get("attendees") or []
    for attendee in attendees:
        if attendee.get("self") and attendee.get("responseStatus") == "declined":
            return True
    return False
