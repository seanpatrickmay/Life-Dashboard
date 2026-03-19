from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition_suggestions import NutritionSuggestion
from app.utils.timezone import eastern_now


STALENESS_HOURS = 6


class NutritionSuggestionsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_user(self, user_id: int) -> NutritionSuggestion | None:
        result = await self.session.execute(
            select(NutritionSuggestion).where(NutritionSuggestion.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_id: int, suggestions: list[dict]) -> NutritionSuggestion:
        row = await self.get_for_user(user_id)
        if row is None:
            row = NutritionSuggestion(user_id=user_id, suggestions=suggestions, stale=False)
            self.session.add(row)
        else:
            row.suggestions = suggestions
            row.stale = False
        await self.session.flush()
        return row

    async def mark_stale(self, user_id: int) -> None:
        await self.session.execute(
            update(NutritionSuggestion)
            .where(NutritionSuggestion.user_id == user_id)
            .values(stale=True)
        )

    def needs_refresh(self, row: NutritionSuggestion | None) -> bool:
        if row is None:
            return True
        if row.stale:
            return True
        cutoff = eastern_now() - timedelta(hours=STALENESS_HOURS)
        return row.updated_at < cutoff
