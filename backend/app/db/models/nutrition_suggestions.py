from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class NutritionSuggestion(Base):
    __tablename__ = "nutrition_suggestions"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), unique=True, nullable=False
    )
    suggestions: Mapped[list[dict]] = mapped_column(JSONB, server_default="[]")
    stale: Mapped[bool] = mapped_column(Boolean, server_default="false")
