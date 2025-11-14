"""Declarative base model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, declared_attr, Mapped, mapped_column

from app.utils.timezone import eastern_now


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:  # type: ignore[override]
        return cls.__name__.lower()

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=eastern_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=eastern_now, onupdate=eastern_now
    )
