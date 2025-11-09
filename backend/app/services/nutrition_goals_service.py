from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.nutrition_goals_repository import NutritionGoalsRepository


class NutritionGoalsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NutritionGoalsRepository(session)

    async def list_goals(self, user_id: int) -> list[dict[str, Any]]:
        nutrients = await self.repo.list_nutrients()
        overrides = await self.repo.get_overrides(user_id)
        override_map = {goal.nutrient_id: goal.daily_goal for goal in overrides}
        return [
            {
                "id": nutrient.id,
                "slug": nutrient.slug,
                "display_name": nutrient.display_name,
                "unit": nutrient.unit,
                "category": nutrient.category.value,
                "group": nutrient.group.value,
                "goal": override_map.get(nutrient.id, nutrient.default_goal),
                "default_goal": nutrient.default_goal,
            }
            for nutrient in nutrients
        ]

    async def upsert_goal(
        self, user_id: int, slug: str, goal_value: float
    ) -> dict[str, Any]:
        nutrient = await self.repo.get_nutrient_by_slug(slug)
        if nutrient is None:
            raise ValueError("Unknown nutrient")
        goal = await self.repo.upsert_goal(user_id, nutrient.id, goal_value)
        await self.session.commit()
        return {
            "slug": nutrient.slug,
            "display_name": nutrient.display_name,
            "unit": nutrient.unit,
            "category": nutrient.category.value,
            "group": nutrient.group.value,
            "goal": goal.daily_goal,
            "default_goal": nutrient.default_goal,
        }
