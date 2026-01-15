"""Journal entry and summary ORM models."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .entities import User


class JournalEntry(Base):
  """Raw journal entry stored temporarily for a local day."""

  __tablename__ = "journal_entry"

  user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
  local_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
  time_zone: Mapped[str] = mapped_column(String(64), nullable=False)
  text: Mapped[str] = mapped_column(Text, nullable=False)

  user: Mapped[User] = relationship(back_populates="journal_entries")


class JournalDaySummary(Base):
  """Compiled daily summary derived from journal entries and completed todos."""

  __tablename__ = "journal_day_summary"
  __table_args__ = (
    UniqueConstraint("user_id", "local_date", name="uq_journal_day_summary_user_date"),
  )

  user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
  local_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
  time_zone: Mapped[str] = mapped_column(String(64), nullable=False)
  status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
  summary_json: Mapped[dict] = mapped_column(JSON)
  finalized_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  model_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
  version: Mapped[str | None] = mapped_column(String(32), nullable=True)

  user: Mapped[User] = relationship(back_populates="journal_summaries")
