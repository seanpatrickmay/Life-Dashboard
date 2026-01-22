"""Link todos with Google Calendar events."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.google_calendar_client import GoogleCalendarClient, GoogleCalendarError
from app.db.models.calendar import CalendarEvent, GoogleCalendar, TodoEventLink
from app.db.models.todo import TodoItem
from app.services.google_calendar_connection_service import GoogleCalendarConnectionService
from app.services.google_calendar_constants import LIFE_DASHBOARD_CALENDAR_NAME
from app.services.todo_calendar_title_agent import TodoCalendarTitleAgent
from app.utils.timezone import resolve_time_zone


GOOGLE_TODO_COLOR_ID = "3"
TODO_DESCRIPTION_TAG = "Life Dashboard Todo"


class TodoCalendarLinkService:
    """Creates and maintains 1:1 links between todos and calendar events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.connection_service = GoogleCalendarConnectionService(session)
        self.title_agent = TodoCalendarTitleAgent()

    async def upsert_event_for_todo(self, todo: TodoItem, *, time_zone: str | None = None) -> None:
        """Create or update the Google Calendar event linked to a todo."""
        if todo.deadline_utc is None:
            await self._unlink_todo(todo, delete_event=True)
            await self.session.commit()
            return
        token = await self.connection_service.get_access_token(todo.user_id)
        if not token:
            return
        calendar = await self._ensure_life_dashboard_calendar(todo.user_id)
        link = await self._get_link(todo.id)
        existing_description = None
        if link and link.google_event_id:
            event = await self._get_event(calendar.id, link.google_event_id)
            existing_description = event.description if event else None

        start_time, end_time, is_all_day = _compute_event_times(
            todo.deadline_utc, time_zone, date_only=todo.deadline_is_date_only
        )
        title = self.title_agent.build_title(todo.text)
        payload = _build_todo_event_payload(
            todo,
            title=title,
            start_time=start_time,
            end_time=end_time,
            time_zone=time_zone,
            is_all_day=is_all_day,
            existing_description=existing_description,
        )
        client = GoogleCalendarClient(token)
        try:
            if link and link.google_event_id:
                event = await client.patch_event(calendar.google_id, link.google_event_id, payload)
            else:
                event = await client.insert_event(calendar.google_id, payload)
        except GoogleCalendarError as exc:
            logger.warning("Failed to sync todo {} to Google Calendar: {}", todo.id, exc)
            return

        await self._upsert_link(
            todo,
            calendar,
            event_id=event.get("id"),
            ical_uid=event.get("iCalUID"),
            start_time=start_time,
            end_time=end_time,
        )
        await self.session.commit()

    async def unlink_todo(self, todo: TodoItem, *, delete_event: bool) -> None:
        """Remove any calendar linkage for the todo, optionally deleting the event."""
        await self._unlink_todo(todo, delete_event=delete_event)
        await self.session.commit()

    async def handle_event_deleted(self, calendar_id: int, google_event_id: str | None) -> None:
        """Unlink todos when their Google Calendar events are deleted."""
        if not google_event_id:
            return
        link = await self._get_link_by_event(calendar_id, google_event_id)
        if not link:
            return
        todo = link.todo
        todo.deadline_utc = None
        todo.deadline_is_date_only = False
        await self.session.delete(link)
        await self.session.commit()

    async def handle_event_updated(
        self,
        calendar_id: int,
        google_event_id: str,
        *,
        event_payload: dict[str, Any],
        event_updated_at: datetime | None,
        start_time: datetime | None,
        end_time: datetime | None,
        time_zone: str | None,
    ) -> None:
        """Apply event updates to linked todos using last-write-wins."""
        link = await self._get_link_by_event(calendar_id, google_event_id)
        if not link:
            todo_id = _extract_todo_id(event_payload)
            if todo_id:
                todo = await self.session.get(TodoItem, todo_id)
                calendar = await self.session.get(GoogleCalendar, calendar_id)
                if todo and calendar:
                    await self._upsert_link(
                        todo,
                        calendar,
                        event_id=google_event_id,
                        ical_uid=event_payload.get("iCalUID"),
                        start_time=start_time,
                        end_time=end_time,
                    )
                    await self.session.commit()
            link = await self._get_link_by_event(calendar_id, google_event_id)
        if not link:
            return
        todo = link.todo
        if not event_updated_at or todo.updated_at >= event_updated_at:
            return
        summary = event_payload.get("summary")
        if summary:
            todo.text = summary.strip()
        is_date_only = _is_date_only_todo_event(event_payload)
        if is_date_only:
            deadline = _all_day_deadline(start_time, end_time, time_zone)
            if deadline:
                todo.deadline_utc = deadline
            todo.deadline_is_date_only = True
        elif end_time:
            todo.deadline_utc = end_time
            todo.deadline_is_date_only = False
        await self.session.commit()

    async def _ensure_life_dashboard_calendar(self, user_id: int) -> GoogleCalendar:
        calendar = await self._get_life_dashboard_calendar(user_id)
        if calendar:
            calendar.selected = True
            calendar.is_life_dashboard = True
            await self.session.commit()
            return calendar
        connection = await self.connection_service.get_connection(user_id)
        if not connection:
            raise RuntimeError("Google Calendar connection not found.")
        token = await self.connection_service.get_access_token(user_id)
        if not token:
            raise RuntimeError("Google Calendar connection missing or expired.")
        client = GoogleCalendarClient(token)
        created = await client.create_calendar(
            summary=LIFE_DASHBOARD_CALENDAR_NAME,
            description="Life Dashboard todos and planning",
        )
        calendar = GoogleCalendar(
            user_id=user_id,
            connection_id=connection.id,
            google_id=created.get("id"),
            summary=created.get("summary") or LIFE_DASHBOARD_CALENDAR_NAME,
            description=created.get("description"),
            time_zone=created.get("timeZone"),
            access_role=created.get("accessRole"),
            primary=bool(created.get("primary")),
            selected=True,
            is_life_dashboard=True,
            color_id=created.get("colorId"),
        )
        self.session.add(calendar)
        await self.session.commit()
        return calendar

    async def _get_life_dashboard_calendar(self, user_id: int) -> GoogleCalendar | None:
        stmt = select(GoogleCalendar).where(
            GoogleCalendar.user_id == user_id,
            GoogleCalendar.summary == LIFE_DASHBOARD_CALENDAR_NAME,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_link(self, todo_id: int) -> TodoEventLink | None:
        stmt = select(TodoEventLink).where(TodoEventLink.todo_id == todo_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_link_by_event(
        self, calendar_id: int, google_event_id: str
    ) -> TodoEventLink | None:
        stmt = select(TodoEventLink).where(
            TodoEventLink.calendar_id == calendar_id,
            TodoEventLink.google_event_id == google_event_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_event(self, calendar_id: int, google_event_id: str) -> CalendarEvent | None:
        stmt = select(CalendarEvent).where(
            CalendarEvent.calendar_id == calendar_id,
            CalendarEvent.google_event_id == google_event_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_link(
        self,
        todo: TodoItem,
        calendar: GoogleCalendar,
        *,
        event_id: str | None,
        ical_uid: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> None:
        link = await self._get_link(todo.id)
        if link is None:
            link = TodoEventLink(
                user_id=todo.user_id,
                todo_id=todo.id,
                calendar_id=calendar.id,
            )
            self.session.add(link)
        link.calendar_id = calendar.id
        link.google_event_id = event_id
        link.ical_uid = ical_uid
        link.event_start_time = start_time
        link.event_end_time = end_time
        link.last_synced_at = datetime.now(timezone.utc)

    async def _unlink_todo(self, todo: TodoItem, *, delete_event: bool) -> None:
        link = await self._get_link(todo.id)
        if not link:
            return
        if delete_event and link.google_event_id:
            token = await self.connection_service.get_access_token(todo.user_id)
            if token:
                calendar = await self.session.get(GoogleCalendar, link.calendar_id)
                if calendar:
                    client = GoogleCalendarClient(token)
                    try:
                        await client.delete_event(calendar.google_id, link.google_event_id)
                    except GoogleCalendarError as exc:
                        logger.warning("Failed to delete Google Calendar event {}: {}", link.google_event_id, exc)
        await self.session.delete(link)


def _compute_event_times(
    deadline_utc: datetime, time_zone: str | None, *, date_only: bool
) -> tuple[datetime, datetime, bool]:
    tz_name = (time_zone or "UTC").strip() or "UTC"
    zone = resolve_time_zone(tz_name)
    deadline_local = deadline_utc.astimezone(zone)
    if date_only:
        start_local = deadline_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        return start_local, end_local, True
    start_local = deadline_local - timedelta(minutes=30)
    return start_local, deadline_local, False


def _build_todo_event_payload(
    todo: TodoItem,
    *,
    title: str,
    start_time: datetime,
    end_time: datetime,
    time_zone: str | None,
    is_all_day: bool,
    existing_description: str | None,
) -> dict[str, Any]:
    description = _ensure_description_tag(existing_description)
    tz_name = (time_zone or "UTC").strip() or "UTC"
    if is_all_day:
        start_payload = {"date": start_time.date().isoformat()}
        end_payload = {"date": end_time.date().isoformat()}
    else:
        start_payload = {"dateTime": start_time.isoformat(), "timeZone": tz_name}
        end_payload = {"dateTime": end_time.isoformat(), "timeZone": tz_name}
    return {
        "summary": title,
        "description": description,
        "start": start_payload,
        "end": end_payload,
        "colorId": GOOGLE_TODO_COLOR_ID,
        "extendedProperties": {"private": {"life_dashboard_todo": "true", "todo_id": str(todo.id)}},
    }


def _ensure_description_tag(existing: str | None) -> str:
    if not existing:
        return TODO_DESCRIPTION_TAG
    if TODO_DESCRIPTION_TAG in existing:
        return existing
    return f"{existing}\n{TODO_DESCRIPTION_TAG}"


def _is_date_only_todo_event(payload: dict[str, Any]) -> bool:
    description = payload.get("description") or ""
    if TODO_DESCRIPTION_TAG not in description and not _has_todo_marker(payload):
        return False
    start = payload.get("start") or {}
    end = payload.get("end") or {}
    return "date" in start and "date" in end


def _all_day_deadline(
    start_time: datetime | None, end_time: datetime | None, time_zone: str | None
) -> datetime | None:
    if not start_time and not end_time:
        return None
    tz_name = (time_zone or "UTC").strip() or "UTC"
    zone = resolve_time_zone(tz_name)
    if start_time:
        local_date = start_time.astimezone(zone).date()
    else:
        local_date = (end_time - timedelta(seconds=1)).astimezone(zone).date()
    due_local = datetime.combine(local_date, time(23, 59), tzinfo=zone)
    return due_local.astimezone(timezone.utc)


def _extract_todo_id(payload: dict[str, Any]) -> int | None:
    extended = payload.get("extendedProperties") or {}
    private = extended.get("private") or {}
    raw = private.get("todo_id")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _has_todo_marker(payload: dict[str, Any]) -> bool:
    extended = payload.get("extendedProperties") or {}
    private = extended.get("private") or {}
    return private.get("life_dashboard_todo") == "true"
