"""Todo list ORM models."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .entities import User

VALID_TIME_HORIZONS = ("this_week", "this_month", "this_year")


class TodoItem(Base):
  """Per-user to-do item with optional UTC deadline."""

  __tablename__ = "todo_item"
  __table_args__ = (
    CheckConstraint(
      "time_horizon IN ('this_week', 'this_month', 'this_year')",
      name="ck_todo_item_time_horizon",
    ),
  )

  user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
  project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
  text: Mapped[str] = mapped_column(String(512))
  completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
  deadline_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
  deadline_is_date_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  time_horizon: Mapped[str] = mapped_column(String(16), nullable=False, default="this_week", index=True)
  completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  completed_local_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
  completed_time_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
  accomplishment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
  accomplishment_generated_at_utc: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
  )

  user: Mapped[User] = relationship(back_populates="todos")
  project: Mapped["Project"] = relationship(back_populates="todos")
  calendar_link: Mapped["TodoEventLink | None"] = relationship(
    back_populates="todo", uselist=False
  )
  project_suggestion: Mapped["TodoProjectSuggestion | None"] = relationship(
    back_populates="todo", uselist=False
  )

  def mark_completed(self, done: bool, *, completed_at_utc: datetime | None = None) -> None:
    """Set completion flag and timestamp."""
    self.completed = done
    if done:
      self.completed_at_utc = completed_at_utc or datetime.now(timezone.utc)
    else:
      self.completed_at_utc = None
