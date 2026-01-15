"""Journal entry and summary persistence helpers."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journal import JournalDaySummary, JournalEntry


class JournalRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def create_entry(
    self,
    user_id: int,
    local_date: date,
    time_zone: str,
    text: str,
    created_at: datetime,
  ) -> JournalEntry:
    entry = JournalEntry(
      user_id=user_id,
      local_date=local_date,
      time_zone=time_zone,
      text=text,
      created_at=created_at,
      updated_at=created_at,
    )
    self.session.add(entry)
    return entry

  async def list_entries_for_day(self, user_id: int, local_date: date) -> list[JournalEntry]:
    stmt = (
      select(JournalEntry)
      .where(JournalEntry.user_id == user_id, JournalEntry.local_date == local_date)
      .order_by(JournalEntry.created_at.asc())
    )
    result = await self.session.execute(stmt)
    return list(result.scalars().all())

  async def delete_entries_for_day(self, user_id: int, local_date: date) -> None:
    await self.session.execute(
      delete(JournalEntry).where(
        JournalEntry.user_id == user_id, JournalEntry.local_date == local_date
      )
    )

  async def get_summary_for_day(self, user_id: int, local_date: date) -> JournalDaySummary | None:
    stmt = select(JournalDaySummary).where(
      JournalDaySummary.user_id == user_id, JournalDaySummary.local_date == local_date
    )
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()

  async def create_summary(
    self,
    *,
    user_id: int,
    local_date: date,
    time_zone: str,
    status: str,
    summary_json: dict,
    finalized_at: datetime | None,
    model_name: str | None,
    version: str | None,
  ) -> JournalDaySummary:
    summary = JournalDaySummary(
      user_id=user_id,
      local_date=local_date,
      time_zone=time_zone,
      status=status,
      summary_json=summary_json,
      finalized_at_utc=finalized_at,
      model_name=model_name,
      version=version,
    )
    self.session.add(summary)
    return summary

  async def update_summary(
    self,
    summary: JournalDaySummary,
    *,
    status: str,
    summary_json: dict,
    finalized_at: datetime | None,
    model_name: str | None,
    version: str | None,
  ) -> JournalDaySummary:
    summary.status = status
    summary.summary_json = summary_json
    summary.finalized_at_utc = finalized_at
    summary.model_name = model_name
    summary.version = version
    return summary

  async def list_entry_counts(self, user_id: int, start: date, end: date) -> dict[date, int]:
    stmt = (
      select(JournalEntry.local_date, func.count(JournalEntry.id))
      .where(
        JournalEntry.user_id == user_id,
        JournalEntry.local_date >= start,
        JournalEntry.local_date <= end,
      )
      .group_by(JournalEntry.local_date)
    )
    result = await self.session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}

  async def list_summary_counts(self, user_id: int, start: date, end: date) -> dict[date, int]:
    stmt = (
      select(JournalDaySummary.local_date, func.count(JournalDaySummary.id))
      .where(
        JournalDaySummary.user_id == user_id,
        JournalDaySummary.local_date >= start,
        JournalDaySummary.local_date <= end,
      )
      .group_by(JournalDaySummary.local_date)
    )
    result = await self.session.execute(stmt)
    return {row[0]: row[1] for row in result.all()}
