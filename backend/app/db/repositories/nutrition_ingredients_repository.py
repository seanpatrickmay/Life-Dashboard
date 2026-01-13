from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.nutrition import (
    NutritionIngredient,
    NutritionIngredientProfile,
    NutritionIngredientStatus,
    NutritionRecipe,
    NutritionRecipeComponent,
    NUTRIENT_DEFINITIONS,
)


class NutritionIngredientsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_ingredients(self, owner_user_id: int) -> list[NutritionIngredient]:
        stmt = (
            select(NutritionIngredient)
            .where(NutritionIngredient.owner_user_id == owner_user_id)
            .options(selectinload(NutritionIngredient.profile))
            .order_by(NutritionIngredient.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_ingredient(
        self, ingredient_id: int, owner_user_id: int
    ) -> NutritionIngredient | None:
        stmt = (
            select(NutritionIngredient)
            .where(
                NutritionIngredient.id == ingredient_id,
                NutritionIngredient.owner_user_id == owner_user_id,
            )
            .options(selectinload(NutritionIngredient.profile))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_ingredient_by_name(self, owner_user_id: int, name: str) -> NutritionIngredient | None:
        stmt = (
            select(NutritionIngredient)
            .where(
                NutritionIngredient.owner_user_id == owner_user_id,
                sa.func.lower(NutritionIngredient.name) == sa.func.lower(sa.literal(name)),
            )
            .options(selectinload(NutritionIngredient.profile))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recipe_by_name(self, owner_user_id: int, name: str) -> NutritionRecipe | None:
        stmt = (
            select(NutritionRecipe)
            .where(
                NutritionRecipe.owner_user_id == owner_user_id,
                sa.func.lower(NutritionRecipe.name) == sa.func.lower(sa.literal(name)),
            )
            .options(selectinload(NutritionRecipe.components))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_ingredient(
        self,
        name: str,
        default_unit: str,
        source: str | None,
        nutrient_values: dict[str, float | None],
        owner_user_id: int,
        status: NutritionIngredientStatus = NutritionIngredientStatus.UNCONFIRMED,
    ) -> NutritionIngredient:
        profile_kwargs = {
            definition.column_name: nutrient_values.get(definition.slug)
            for definition in NUTRIENT_DEFINITIONS
        }
        profile = NutritionIngredientProfile(**profile_kwargs)
        self.session.add(profile)
        await self.session.flush()

        ingredient = NutritionIngredient(
            name=name,
            default_unit=default_unit,
            source=source,
            status=status,
            owner_user_id=owner_user_id,
            profile=profile,
        )
        self.session.add(ingredient)
        await self.session.flush()
        return ingredient

    async def update_ingredient(
        self,
        ingredient: NutritionIngredient,
        *,
        name: str | None = None,
        default_unit: str | None = None,
        status: NutritionIngredientStatus | None = None,
        nutrient_values: dict[str, float | None] | None = None,
    ) -> NutritionIngredient:
        if name:
            ingredient.name = name
        if default_unit:
            ingredient.default_unit = default_unit
        if status:
            ingredient.status = status
        if nutrient_values:
            for definition in NUTRIENT_DEFINITIONS:
                value = nutrient_values.get(definition.slug)
                if value is not None:
                    setattr(ingredient.profile, definition.column_name, value)
        return ingredient


class NutritionRecipesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_recipes(self, owner_user_id: int | None, load_components: bool = False) -> list[NutritionRecipe]:
        stmt = select(NutritionRecipe)
        if owner_user_id is not None:
            stmt = stmt.where(NutritionRecipe.owner_user_id == owner_user_id)
        if load_components:
            stmt = stmt.options(
                selectinload(NutritionRecipe.components)
                .selectinload(NutritionRecipeComponent.ingredient)
                .selectinload(NutritionIngredient.profile),
                selectinload(NutritionRecipe.components).selectinload(
                    NutritionRecipeComponent.child_recipe
                ),
            )
        stmt = stmt.order_by(NutritionRecipe.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recipe(
        self, recipe_id: int, owner_user_id: int, load_components: bool = True
    ) -> NutritionRecipe | None:
        stmt = (
            select(NutritionRecipe)
            .where(
                NutritionRecipe.id == recipe_id,
                NutritionRecipe.owner_user_id == owner_user_id,
            )
        )
        if load_components:
            stmt = stmt.options(
                selectinload(NutritionRecipe.components)
                .selectinload(NutritionRecipeComponent.ingredient)
                .selectinload(NutritionIngredient.profile),
                selectinload(NutritionRecipe.components).selectinload(
                    NutritionRecipeComponent.child_recipe
                ),
            )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recipe_by_name(self, owner_user_id: int, name: str) -> NutritionRecipe | None:
        stmt = (
            select(NutritionRecipe)
            .where(
                NutritionRecipe.owner_user_id == owner_user_id,
                sa.func.lower(NutritionRecipe.name) == sa.func.lower(sa.literal(name)),
            )
            .options(
                selectinload(NutritionRecipe.components)
                .selectinload(NutritionRecipeComponent.ingredient)
                .selectinload(NutritionIngredient.profile),
                selectinload(NutritionRecipe.components).selectinload(
                    NutritionRecipeComponent.child_recipe
                ),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_recipe(
        self,
        *,
        name: str,
        default_unit: str,
        servings: float,
        status: NutritionIngredientStatus,
        owner_user_id: int,
        components: list[dict],
        source: str | None = None,
    ) -> NutritionRecipe:
        recipe = NutritionRecipe(
            name=name,
            default_unit=default_unit,
            servings=servings,
            status=status,
            owner_user_id=owner_user_id,
            source=source,
        )
        self.session.add(recipe)
        await self.session.flush()

        for position, component in enumerate(components):
            self.session.add(
                NutritionRecipeComponent(
                    recipe_id=recipe.id,
                    ingredient_id=component.get("ingredient_id"),
                    child_recipe_id=component.get("child_recipe_id"),
                    quantity=component["quantity"],
                    unit=component["unit"],
                    position=component.get("position", position),
                )
            )

        await self.session.flush()
        return recipe

    async def replace_components(self, recipe: NutritionRecipe, components: list[dict]) -> None:
        await self.session.execute(
            sa.delete(NutritionRecipeComponent).where(NutritionRecipeComponent.recipe_id == recipe.id)
        )
        await self.session.flush()
        for position, component in enumerate(components):
            self.session.add(
                NutritionRecipeComponent(
                    recipe_id=recipe.id,
                    ingredient_id=component.get("ingredient_id"),
                    child_recipe_id=component.get("child_recipe_id"),
                    quantity=component["quantity"],
                    unit=component["unit"],
                    position=component.get("position", position),
                )
            )
        await self.session.flush()

    async def update_recipe(
        self,
        recipe: NutritionRecipe,
        *,
        name: str | None = None,
        default_unit: str | None = None,
        servings: float | None = None,
        status: NutritionIngredientStatus | None = None,
        components: list[dict] | None = None,
    ) -> NutritionRecipe:
        if name:
            recipe.name = name
        if default_unit:
            recipe.default_unit = default_unit
        if servings:
            recipe.servings = servings
        if status:
            recipe.status = status
        if components is not None:
            await self.replace_components(recipe, components)
        return recipe
