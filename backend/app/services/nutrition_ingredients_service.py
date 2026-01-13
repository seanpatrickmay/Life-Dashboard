from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import (
    NUTRIENT_DEFINITIONS,
    NutritionIngredient,
    NutritionIngredientStatus,
)
from app.db.repositories.nutrition_ingredients_repository import NutritionIngredientsRepository


class NutritionIngredientsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NutritionIngredientsRepository(session)

    async def list_ingredients(self, owner_user_id: int) -> list[dict[str, Any]]:
        ingredients = await self.repo.list_ingredients(owner_user_id)
        return [self._serialize_ingredient(item) for item in ingredients]

    async def create_ingredient(
        self,
        *,
        name: str,
        default_unit: str,
        source: str | None,
        nutrient_values: dict[str, float | None],
        owner_user_id: int,
        status: NutritionIngredientStatus = NutritionIngredientStatus.UNCONFIRMED,
    ) -> dict[str, Any]:
        ingredient = await self.repo.create_ingredient(
            name, default_unit, source, nutrient_values, owner_user_id, status
        )
        await self.session.commit()
        return self._serialize_ingredient(ingredient)

    async def update_ingredient(
        self,
        ingredient_id: int,
        *,
        owner_user_id: int,
        name: str | None = None,
        default_unit: str | None = None,
        status: NutritionIngredientStatus | None = None,
        nutrient_values: dict[str, float | None] | None = None,
    ) -> dict[str, Any]:
        ingredient = await self.repo.get_ingredient(ingredient_id, owner_user_id)
        if ingredient is None:
            raise ValueError("Ingredient not found")
        await self.repo.update_ingredient(
            ingredient,
            name=name,
            default_unit=default_unit,
            status=status,
            nutrient_values=nutrient_values,
        )
        await self.session.commit()
        return self._serialize_ingredient(ingredient)

    def _serialize_ingredient(self, ingredient: NutritionIngredient) -> dict[str, Any]:
        return {
            "id": ingredient.id,
            "owner_user_id": ingredient.owner_user_id,
            "name": ingredient.name,
            "default_unit": ingredient.default_unit,
            "status": ingredient.status.value,
            "source": ingredient.source,
            "nutrients": {
                definition.slug: getattr(ingredient.profile, definition.column_name)
                for definition in NUTRIENT_DEFINITIONS
            },
        }
