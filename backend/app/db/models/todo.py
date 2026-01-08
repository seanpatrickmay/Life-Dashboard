"""Todo list ORM models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .entities import User


class TodoItem(Base):
  """Per-user to-do item with optional UTC deadline."""

  __tablename__ = "todo_item"

  user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
  text: Mapped[str] = mapped_column(String(512))
  completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
  deadline_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
  completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

  user: Mapped[User] = relationship(back_populates="todos")

  def mark_completed(self, done: bool) -> None:
    """Set completion flag and timestamp."""
    self.completed = done
    if done:
      self.completed_at_utc = datetime.now(timezone.utc)
    else:
      self.completed_at_utc = None

