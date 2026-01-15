"""Journal entry capture and day summary compilation."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.journal_repository import JournalRepository
from app.db.repositories.todo_repository import TodoRepository
from app.services.journal_compiler import JournalCompiler
from app.utils.timezone import local_today


class JournalService:
  """Orchestrates journal entry storage and summary compilation."""

  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.journal_repo = JournalRepository(session)
    self.todo_repo = TodoRepository(session)
    self.compiler = JournalCompiler(session)

  async def add_entry(self, *, user_id: int, text: str, time_zone: str) -> dict[str, Any]:
    local_date = local_today(time_zone)
    now_utc = datetime.now(timezone.utc)
    entry = await self.journal_repo.create_entry(
      user_id=user_id,
      local_date=local_date,
      time_zone=time_zone,
      text=text,
      created_at=now_utc,
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
    if summary and summary.status == "final":
      return summary

    entries = await self.journal_repo.list_entries_for_day(user_id, local_date)
    completed = await self.todo_repo.list_completed_for_day(user_id, local_date)
    effective_time_zone = time_zone
    if summary:
      effective_time_zone = summary.time_zone
    elif entries:
      effective_time_zone = entries[0].time_zone
    todo_items = [item.accomplishment_text or item.text for item in completed]
    entry_texts = [entry.text for entry in entries]

    now_utc = datetime.now(timezone.utc)
    summary_payload = {"groups": []}
    status = "final"
    model_name = None
    try:
      summary_payload = await self.compiler.compile_day(
        local_date=local_date,
        time_zone=effective_time_zone,
        entries=entry_texts,
        todo_items=todo_items,
      )
      model_name = self.compiler.model_name
    except Exception as exc:  # noqa: BLE001
      logger.exception(
        "[journal] failed to compile summary user=%s date=%s: %s",
        user_id,
        local_date,
        exc,
      )
      status = "error"

    if summary:
      await self.journal_repo.update_summary(
        summary,
        status=status,
        summary_json=summary_payload,
        finalized_at=now_utc if status == "final" else None,
        model_name=model_name,
        version=self.compiler.VERSION,
      )
    else:
      summary = await self.journal_repo.create_summary(
        user_id=user_id,
        local_date=local_date,
        time_zone=effective_time_zone,
        status=status,
        summary_json=summary_payload,
        finalized_at=now_utc if status == "final" else None,
        model_name=model_name,
        version=self.compiler.VERSION,
      )

    if status == "final":
      await self.journal_repo.delete_entries_for_day(user_id, local_date)
    return summary
