"""Garmin OAuth token store — encrypted blob per user."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, synonym

from .base import Base


class GarminToken(Base):
    """One row per user; holds the tarball of garth token files, Fernet-encrypted."""

    __tablename__ = "garmin_token"

    # Override the Base id: user_id IS the primary key (one token set per user).
    # The underlying column is named "user_id"; `id` is the Python attribute
    # used by session.get(GarminToken, <pk>).
    id: Mapped[int] = mapped_column("user_id", primary_key=True, autoincrement=False)
    user_id: Mapped[int] = synonym("id")  # type: ignore[assignment]
    encrypted_blob: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(  # type: ignore[assignment]
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
