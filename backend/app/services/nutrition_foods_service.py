from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import (
    NUTRIENT_DEFINITIONS,
    NutritionFood,
    NutritionFoodStatus,
)
from app.db.repositories.nutrition_foods_repository import NutritionFoodsRepository


class NutritionFoodsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NutritionFoodsRepository(session)

    async def list_foods(self) -> list[dict[str, Any]]:
        foods = await self.repo.list_foods()
        return [self._serialize_food(food) for food in foods]

    async def create_food(
        self,
        *,
        name: str,
        default_unit: str,
        source: str | None,
        nutrient_values: dict[str, float | None],
        status: NutritionFoodStatus = NutritionFoodStatus.UNCONFIRMED,
    ) -> dict[str, Any]:
        food = await self.repo.create_food(
            name, default_unit, source, nutrient_values, status
        )
        await self.session.commit()
        return self._serialize_food(food)

    async def update_food(
        self,
        food_id: int,
        *,
        name: str | None = None,
        default_unit: str | None = None,
        status: NutritionFoodStatus | None = None,
        nutrient_values: dict[str, float | None] | None = None,
    ) -> dict[str, Any]:
        food = await self.repo.get_food(food_id)
        if food is None:
            raise ValueError("Food not found")
        await self.repo.update_food(
            food,
            name=name,
            default_unit=default_unit,
            status=status,
            nutrient_values=nutrient_values,
        )
        await self.session.commit()
        return self._serialize_food(food)

    def _serialize_food(self, food: NutritionFood) -> dict[str, Any]:
        return {
            "id": food.id,
            "name": food.name,
            "default_unit": food.default_unit,
            "status": food.status.value,
            "source": food.source,
            "nutrients": {
                definition.slug: getattr(food.profile, definition.column_name)
                for definition in NUTRIENT_DEFINITIONS
            },
        }
