from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import NutritionNutrient, NutritionUserGoal


class NutritionGoalsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_nutrients(self) -> list[NutritionNutrient]:
        stmt = select(NutritionNutrient).order_by(NutritionNutrient.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_nutrient_by_slug(self, slug: str) -> NutritionNutrient | None:
        stmt = select(NutritionNutrient).where(NutritionNutrient.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_overrides(self, user_id: int) -> list[NutritionUserGoal]:
        stmt = select(NutritionUserGoal).where(NutritionUserGoal.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_goal(self, user_id: int, nutrient_id: int, daily_goal: float) -> NutritionUserGoal:
        stmt = select(NutritionUserGoal).where(
            NutritionUserGoal.user_id == user_id,
            NutritionUserGoal.nutrient_id == nutrient_id,
        )
        result = await self.session.execute(stmt)
        goal = result.scalar_one_or_none()
        if goal is None:
            goal = NutritionUserGoal(user_id=user_id, nutrient_id=nutrient_id, daily_goal=daily_goal)
            self.session.add(goal)
        else:
            goal.daily_goal = daily_goal
        return goal
