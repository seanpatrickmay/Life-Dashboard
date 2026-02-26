"""Project and todo suggestion ORM models."""
from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .entities import User


class Project(Base):
  """Per-user project bucket that groups todos."""

  __tablename__ = "project"
  __table_args__ = (UniqueConstraint("user_id", "name", name="uq_project_user_name"),)

  user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
  name: Mapped[str] = mapped_column(String(255), nullable=False)
  notes: Mapped[str | None] = mapped_column(Text, nullable=True)
  archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
  sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

  user: Mapped[User] = relationship(back_populates="projects")
  todos: Mapped[list["TodoItem"]] = relationship(back_populates="project")


class TodoProjectSuggestion(Base):
  """Suggested project assignment for a todo when confidence is low."""

  __tablename__ = "todo_project_suggestion"
  __table_args__ = (UniqueConstraint("todo_id", name="uq_todo_project_suggestion_todo"),)

  user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
  todo_id: Mapped[int] = mapped_column(ForeignKey("todo_item.id"), nullable=False, index=True)
  suggested_project_name: Mapped[str] = mapped_column(String(255), nullable=False)
  confidence: Mapped[float] = mapped_column(Float, nullable=False)
  reason: Mapped[str | None] = mapped_column(Text, nullable=True)

  user: Mapped[User] = relationship(back_populates="todo_project_suggestions")
  todo: Mapped["TodoItem"] = relationship(back_populates="project_suggestion")
