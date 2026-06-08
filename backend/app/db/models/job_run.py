"""Durable throttle/state record for background job controllers."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, synonym

from .base import Base


class JobRun(Base):
    """One row per job name; tracks running state and cooldown for Lambda-safe throttle."""

    __tablename__ = "job_run"

    # Override Base id: job_name IS the primary key (one row per logical job).
    # The underlying column is named "job_name"; `id` is the Python attribute
    # used by session.get(JobRun, <pk>).
    id: Mapped[str] = mapped_column("job_name", primary_key=True, autoincrement=False)
    job_name: Mapped[str] = synonym("id")  # type: ignore[assignment]

    running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_allowed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
