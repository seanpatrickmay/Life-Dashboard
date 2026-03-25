"""Models for Claude Code sync tracking and project activity."""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ClaudeCodeSyncCursor(Base):
    __tablename__ = "claude_code_sync_cursor"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", name="uq_cc_cursor_user_session"),
        Index("ix_cc_cursor_user_id", "user_id"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_mtime: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    user = relationship("User", back_populates="claude_code_sync_cursors")


class ProjectActivity(Base):
    __tablename__ = "project_activity"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", name="uq_project_activity_user_session"),
        Index("ix_project_activity_user_project_date", "user_id", "project_id", "local_date"),
        Index("ix_project_activity_user_id", "user_id"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_project_path: Mapped[str] = mapped_column(Text, nullable=False)

    user = relationship("User", back_populates="project_activities")
    project = relationship("Project", back_populates="project_activities")
