"""Project note ORM models."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ProjectNote(Base):
  __tablename__ = "project_note"

  user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
  project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False, index=True)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  body_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
  tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
  archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
  pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


project_note_todo_ref = Table(
  "project_note_todo_ref",
  Base.metadata,
  Column("note_id", Integer, ForeignKey("project_note.id"), primary_key=True),
  Column("todo_id", Integer, ForeignKey("todo_item.id"), primary_key=True),
  Column("user_id", Integer, ForeignKey("user.id"), nullable=False, index=True),
)
