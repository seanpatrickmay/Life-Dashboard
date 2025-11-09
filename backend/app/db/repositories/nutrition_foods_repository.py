from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.nutrition import (
    NutritionFood,
    NutritionFoodProfile,
    NutritionFoodStatus,
    NUTRIENT_DEFINITIONS,
)


class NutritionFoodsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_foods(self) -> list[NutritionFood]:
        stmt = select(NutritionFood).options(selectinload(NutritionFood.profile)).order_by(NutritionFood.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_food(self, food_id: int) -> NutritionFood | None:
        stmt = (
            select(NutritionFood)
            .where(NutritionFood.id == food_id)
            .options(selectinload(NutritionFood.profile))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_food_by_name(self, name: str) -> NutritionFood | None:
        stmt = (
            select(NutritionFood)
            .where(sa.func.lower(NutritionFood.name) == sa.func.lower(sa.literal(name)))
            .options(selectinload(NutritionFood.profile))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_food(
        self,
        name: str,
        default_unit: str,
        source: str | None,
        nutrient_values: dict[str, float | None],
        status: NutritionFoodStatus = NutritionFoodStatus.UNCONFIRMED,
    ) -> NutritionFood:
        profile_kwargs = {
            definition.column_name: nutrient_values.get(definition.slug)
            for definition in NUTRIENT_DEFINITIONS
        }
        profile = NutritionFoodProfile(**profile_kwargs)
        self.session.add(profile)
        await self.session.flush()

        food = NutritionFood(name=name, default_unit=default_unit, source=source, status=status, profile=profile)
        self.session.add(food)
        await self.session.flush()
        return food

    async def update_food(
        self,
        food: NutritionFood,
        *,
        name: str | None = None,
        default_unit: str | None = None,
        status: NutritionFoodStatus | None = None,
        nutrient_values: dict[str, float | None] | None = None,
    ) -> NutritionFood:
        if name:
            food.name = name
        if default_unit:
            food.default_unit = default_unit
        if status:
            food.status = status
        if nutrient_values:
            for definition in NUTRIENT_DEFINITIONS:
                value = nutrient_values.get(definition.slug)
                if value is not None:
                    setattr(food.profile, definition.column_name, value)
        return food
