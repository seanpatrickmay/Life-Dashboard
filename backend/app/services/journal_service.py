"""Journal entry capture and day summary compilation."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.calendar import CalendarEvent, GoogleCalendar, TodoEventLink
from app.db.repositories.journal_repository import JournalRepository
from app.db.repositories.todo_repository import TodoRepository
from app.services.journal_compiler import JournalCompiler
from app.utils.timezone import local_today, resolve_time_zone


class JournalService:
  """Orchestrates journal entry storage and summary compilation."""

  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.journal_repo = JournalRepository(session)
    self.todo_repo = TodoRepository(session)
    self.compiler = JournalCompiler(session)

  async def add_entry(
    self,
    *,
    user_id: int,
    text: str,
    time_zone: str,
    occurred_at_utc: datetime | None = None,
  ) -> dict[str, Any]:
    effective_time = occurred_at_utc.astimezone(timezone.utc) if occurred_at_utc else datetime.now(timezone.utc)
    local_date = effective_time.astimezone(resolve_time_zone(time_zone)).date() if occurred_at_utc else local_today(time_zone)
    entry = await self.journal_repo.create_entry(
      user_id=user_id,
      local_date=local_date,
      time_zone=time_zone,
      text=text,
      created_at=effective_time,
    )
    return {
      "entry": entry,
      "local_date": local_date,
    }

  async def fetch_day(
    self,
    *,
    user_id: int,
    local_date: date,
    time_zone: str,
  ) -> dict[str, Any]:
    today = local_today(time_zone)
    if local_date >= today:
      await self._ensure_summary(
        user_id=user_id,
        local_date=today - timedelta(days=1),
        time_zone=time_zone,
      )
      entries = await self.journal_repo.list_entries_for_day(user_id, local_date)
      completed = await self.todo_repo.list_completed_for_day(user_id, local_date)
      return {
        "status": "open",
        "entries": entries,
        "completed_items": completed,
        "summary": None,
      }
    summary = await self._ensure_summary(user_id=user_id, local_date=local_date, time_zone=time_zone)
    return {
      "status": summary.status if summary else "final",
      "entries": [],
      "completed_items": [],
      "summary": summary.summary_json if summary else {"groups": []},
    }

  async def fetch_week(
    self, *, user_id: int, week_start: date, week_end: date
  ) -> list[dict[str, Any]]:
    entry_counts = await self.journal_repo.list_entry_counts(user_id, week_start, week_end)
    summary_counts = await self.journal_repo.list_summary_counts(user_id, week_start, week_end)
    completed_counts = await self._list_completed_counts(user_id, week_start, week_end)

    days: list[dict[str, Any]] = []
    current = week_start
    while current <= week_end:
      days.append(
        {
          "local_date": current,
          "has_entries": entry_counts.get(current, 0) > 0,
          "has_summary": summary_counts.get(current, 0) > 0,
          "completed_count": completed_counts.get(current, 0),
        }
      )
      current = current.fromordinal(current.toordinal() + 1)
    return days

  async def _list_completed_counts(
    self, user_id: int, start: date, end: date
  ) -> dict[date, int]:
    counts: dict[date, int] = {}
    current = start
    while current <= end:
      items = await self.todo_repo.list_completed_for_day(user_id, current)
      counts[current] = len(items)
      current = current.fromordinal(current.toordinal() + 1)
    return counts

  async def _ensure_summary(
    self, *, user_id: int, local_date: date, time_zone: str
  ) -> Any:
    summary = await self.journal_repo.get_summary_for_day(user_id, local_date)
    entries = await self.journal_repo.list_entries_for_day(user_id, local_date)
    completed = await self.todo_repo.list_completed_for_day(user_id, local_date)

    effective_time_zone = time_zone
    if summary:
      effective_time_zone = summary.time_zone
    elif entries:
      effective_time_zone = entries[0].time_zone

    zone = resolve_time_zone(effective_time_zone)
    compiler_entries = self._serialize_entries_for_compile(entries, zone)
    compiler_todos = self._serialize_completed_for_compile(completed, zone)
    calendar_events = await self._list_calendar_events_for_day(
      user_id=user_id,
      local_date=local_date,
      time_zone=effective_time_zone,
    )
    source_hash = self._build_source_hash(
      local_date=local_date,
      time_zone=effective_time_zone,
      entries=compiler_entries,
      completed=compiler_todos,
      calendar_events=calendar_events,
    )

    if (
      summary
      and summary.status == "final"
      and summary.version == self.compiler.VERSION
      and summary.source_hash == source_hash
    ):
      return summary

    # Expire cached ORM state before the LLM compile step so the session
    # can be reused afterwards without stale data.
    self.session.expire_all()

    now_utc = datetime.now(timezone.utc)
    summary_payload = {"groups": []}
    status = "final"
    model_name = getattr(self.compiler, "model_name", None)
    try:
      summary_payload = await self.compiler.compile_day(
        local_date=local_date,
        time_zone=effective_time_zone,
        entries=compiler_entries,
        todo_items=compiler_todos,
        calendar_events=calendar_events,
      )
    except Exception as exc:  # noqa: BLE001
      logger.exception(
        "[journal] failed to compile summary user={} date={}: {}",
        user_id,
        local_date,
        exc,
      )
      status = "error"

    summary = await self.journal_repo.upsert_summary(
      user_id=user_id,
      local_date=local_date,
      time_zone=effective_time_zone,
      status=status,
      summary_json=summary_payload,
      source_hash=source_hash,
      finalized_at=now_utc if status == "final" else None,
      model_name=model_name,
      version=self.compiler.VERSION,
    )

    if status == "final":
      await self.journal_repo.delete_entries_for_day(user_id, local_date)
    return summary

  def _serialize_entries_for_compile(
    self, entries: list[Any], zone: Any
  ) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for entry in entries:
      created_local = entry.created_at.astimezone(zone) if entry.created_at else None
      payload.append(
        {
          "source_id": f"entry:{entry.id}",
          "text": entry.text,
          "occurred_at_local": created_local.isoformat() if created_local else None,
          "time_label": _format_local_time(created_local) if created_local else "Time unknown",
          "time_precision": "exact" if created_local else "unknown",
        }
      )
    return payload

  def _serialize_completed_for_compile(
    self, completed: list[Any], zone: Any
  ) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in completed:
      completed_local = item.completed_at_utc.astimezone(zone) if item.completed_at_utc else None
      payload.append(
        {
          "source_id": f"todo:{item.id}",
          "text": item.accomplishment_text or item.text,
          "occurred_at_local": completed_local.isoformat() if completed_local else None,
          "time_label": _format_local_time(completed_local) if completed_local else "Time unknown",
          "time_precision": "exact" if completed_local else "unknown",
        }
      )
    return payload

  def _build_source_hash(
    self,
    *,
    local_date: date,
    time_zone: str,
    entries: list[dict[str, Any]],
    completed: list[dict[str, Any]],
    calendar_events: list[dict[str, Any]],
  ) -> str:
    payload = {
      "local_date": local_date.isoformat(),
      "time_zone": time_zone,
      "entries": sorted(entries, key=lambda item: str(item.get("source_id") or "")),
      "completed": sorted(completed, key=lambda item: str(item.get("source_id") or "")),
      "calendar_events": sorted(calendar_events, key=lambda item: str(item.get("source_id") or "")),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

  async def _list_calendar_events_for_day(
    self,
    *,
    user_id: int,
    local_date: date,
    time_zone: str,
  ) -> list[dict[str, Any]]:
    zone = resolve_time_zone(time_zone)
    start_local = datetime.combine(local_date, datetime.min.time(), tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    stmt = (
      select(CalendarEvent, GoogleCalendar, TodoEventLink)
      .join(GoogleCalendar, CalendarEvent.calendar_id == GoogleCalendar.id)
      .outerjoin(
        TodoEventLink,
        (TodoEventLink.calendar_id == CalendarEvent.calendar_id)
        & (TodoEventLink.google_event_id == CalendarEvent.google_event_id),
      )
      .where(
        CalendarEvent.user_id == user_id,
        or_(CalendarEvent.status.is_(None), CalendarEvent.status != "cancelled"),
        CalendarEvent.start_time.is_not(None),
        CalendarEvent.end_time.is_not(None),
        CalendarEvent.start_time >= start_utc,
        CalendarEvent.start_time < end_utc,
        GoogleCalendar.selected.is_(True),
        TodoEventLink.todo_id.is_(None),
      )
      .order_by(CalendarEvent.start_time.asc())
    )
    result = await self.session.execute(stmt)
    rows = result.all()

    events: list[dict[str, Any]] = []
    for event, calendar, link in rows:
      if link and link.todo_id:
        continue
      if _is_declined_attendee(event.attendees):
        continue
      summary = (event.summary or "").strip()
      if not summary:
        continue
      start_time_local = event.start_time.astimezone(zone) if event.start_time else None
      end_time_local = event.end_time.astimezone(zone) if event.end_time else None
      time_precision = "all_day" if event.is_all_day else "range"
      time_label = "All day" if event.is_all_day else _format_local_range(start_time_local, end_time_local)
      events.append(
        {
          "source_id": f"calendar:{event.id}",
          "event_id": event.id,
          "google_event_id": event.google_event_id,
          "summary": summary,
          "location": event.location,
          "calendar": {
            "summary": calendar.summary,
            "primary": calendar.primary,
            "is_life_dashboard": calendar.is_life_dashboard,
          },
          "occurred_at_local": start_time_local.isoformat() if start_time_local else None,
          "start_time_local": start_time_local.isoformat() if start_time_local else None,
          "end_time_local": end_time_local.isoformat() if end_time_local else None,
          "time_label": time_label,
          "time_precision": time_precision,
          "is_all_day": event.is_all_day,
        }
      )
    return events


def _is_declined_attendee(attendees: list[dict[str, object]] | None) -> bool:
  if not attendees:
    return False
  for attendee in attendees:
    if attendee.get("self") and attendee.get("responseStatus") == "declined":
      return True
  return False


def _format_local_time(value: datetime | None) -> str:
  if value is None:
    return "Time unknown"
  return value.strftime("%I:%M %p").lstrip("0")


def _format_local_range(start: datetime | None, end: datetime | None) -> str:
  if start is None or end is None:
    return "Time unknown"
  return f"{_format_local_time(start)} - {_format_local_time(end)}"
