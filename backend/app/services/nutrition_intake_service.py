from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import (
    NUTRIENT_DEFINITIONS,
    NutritionIngredient,
    NutritionIntake,
    NutritionIntakeSource,
    NutritionRecipe,
    NutritionRecipeComponent,
)
from app.db.repositories.nutrition_intake_repository import NutritionIntakeRepository
from app.db.repositories.nutrition_ingredients_repository import (
    NutritionIngredientsRepository,
    NutritionRecipesRepository,
)
from app.services.nutrition_goals_service import NutritionGoalsService
from app.utils.timezone import eastern_today


class NutritionIntakeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NutritionIntakeRepository(session)
        self.ingredients_repo = NutritionIngredientsRepository(session)
        self.recipes_repo = NutritionRecipesRepository(session)
        self.goals_service = NutritionGoalsService(session)

    async def log_manual_intake(
        self,
        *,
        user_id: int,
        ingredient_id: int | None = None,
        recipe_id: int | None = None,
        quantity: float,
        unit: str,
        day: date,
    ) -> dict[str, Any]:
        if bool(ingredient_id) == bool(recipe_id):
            raise ValueError("Provide exactly one of ingredient_id or recipe_id")

        if ingredient_id:
            ingredient = await self.ingredients_repo.get_ingredient(ingredient_id, user_id)
            if ingredient is None:
                raise ValueError("Ingredient not found")
            intake = await self.repo.log_intake(
                user_id=user_id,
                food_id=ingredient_id,
                quantity=quantity,
                unit=unit,
                day=day,
                source=NutritionIntakeSource.MANUAL,
            )
            await self.session.flush()
            await self.session.commit()
            return {
                "id": intake.id,
                "ingredient_id": ingredient_id,
                "day": day,
                "quantity": quantity,
                "unit": unit,
            }

        recipe = await self.recipes_repo.get_recipe(recipe_id, user_id, load_components=True)
        if recipe is None:
            raise ValueError("Recipe not found")
        created = await self._expand_and_log_recipe(
            user_id=user_id,
            recipe=recipe,
            servings=quantity,
            day=day,
            source=NutritionIntakeSource.MANUAL,
        )
        await self.session.commit()
        return created

    async def list_day_menu(self, user_id: int, day: date) -> list[dict[str, Any]]:
        intakes = await self.repo.fetch_for_day_with_food(user_id, day)
        return [self._serialize_entry(intake) for intake in intakes]

    async def update_intake(
        self, intake_id: int, *, owner_user_id: int, quantity: float, unit: str
    ) -> dict[str, Any]:
        intake = await self.repo.update_quantity(
            intake_id,
            owner_user_id=owner_user_id,
            quantity=quantity,
            unit=unit,
        )
        if intake is None:
            raise ValueError("Intake not found")
        await self.session.flush()
        await self.session.commit()
        return self._serialize_entry(intake)

    async def delete_intake(self, intake_id: int, *, owner_user_id: int) -> None:
        await self.repo.delete_intake(intake_id, owner_user_id=owner_user_id)
        await self.session.commit()

    async def daily_summary(self, user_id: int, day: date) -> dict[str, Any]:
        intakes = await self.repo.fetch_for_date(user_id, day)
        totals = self._accumulate(intakes)
        goals = await self.goals_service.list_goals(user_id)
        goal_map = {item["slug"]: item for item in goals}
        nutrients = []
        for definition in NUTRIENT_DEFINITIONS:
            goal_info = goal_map.get(definition.slug)
            goal_value = goal_info["goal"] if goal_info else definition.default_goal
            amount = totals.get(definition.slug, 0.0)
            percent = (amount / goal_value * 100) if goal_value else None
            nutrients.append(
                {
                    "slug": definition.slug,
                    "display_name": definition.display_name,
                    "group": definition.group.value,
                    "unit": definition.unit,
                    "amount": round(amount, 2),
                    "goal": goal_value,
                    "percent_of_goal": (
                        round(percent, 2) if percent is not None else None
                    ),
                }
            )
        return {"date": day, "nutrients": nutrients}

    async def rolling_average(self, user_id: int, days: int = 14) -> dict[str, Any]:
        end = eastern_today()
        start = end - timedelta(days=days - 1)
        intakes = await self.repo.fetch_between(user_id, start, end)
        totals_by_day: dict[date, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for intake in intakes:
            bucket = totals_by_day[intake.day_date]
            profile = intake.ingredient.profile
            for definition in NUTRIENT_DEFINITIONS:
                value = getattr(profile, definition.column_name)
                if value is None:
                    continue
                bucket[definition.slug] += value * intake.quantity

        goals = await self.goals_service.list_goals(user_id)
        goal_map = {item["slug"]: item for item in goals}
        avg_rows = []
        for definition in NUTRIENT_DEFINITIONS:
            goal_value = goal_map.get(definition.slug, {}).get(
                "goal", definition.default_goal
            )
            total_amount = sum(
                day_totals.get(definition.slug, 0.0)
                for day_totals in totals_by_day.values()
            )
            average_amount = total_amount / days if days else 0.0
            percent = (average_amount / goal_value * 100) if goal_value else None
            avg_rows.append(
                {
                    "slug": definition.slug,
                    "display_name": definition.display_name,
                    "group": definition.group.value,
                    "unit": definition.unit,
                    "average_amount": round(average_amount, 2),
                    "goal": goal_value,
                    "percent_of_goal": (
                        round(percent, 2) if percent is not None else None
                    ),
                }
            )
        return {"window_days": days, "nutrients": avg_rows}

    def _accumulate(self, intakes) -> dict[str, float]:
        totals: dict[str, float] = {
            definition.slug: 0.0 for definition in NUTRIENT_DEFINITIONS
        }
        for intake in intakes:
            profile = intake.ingredient.profile
            for definition in NUTRIENT_DEFINITIONS:
                value = getattr(profile, definition.column_name)
                if value is None:
                    continue
                totals[definition.slug] += value * intake.quantity
        return totals

    def _serialize_entry(self, intake: NutritionIntake) -> dict[str, Any]:
        return {
            "id": intake.id,
            "ingredient_id": intake.ingredient_id,
            "ingredient_name": intake.ingredient.name if intake.ingredient else None,
            "quantity": intake.quantity,
            "unit": intake.unit,
            "source": intake.source.value,
        }

    async def _expand_and_log_recipe(
        self,
        *,
        user_id: int,
        recipe: NutritionRecipe,
        servings: float,
        day: date,
        source: NutritionIntakeSource,
    ) -> dict[str, Any]:
        created_entries: list[dict[str, Any]] = []

        async def _expand(target_recipe: NutritionRecipe, multiplier: float) -> None:
            for comp in target_recipe.components:
                per_serving_qty = comp.quantity / target_recipe.servings if target_recipe.servings else comp.quantity
                effective_qty = multiplier * per_serving_qty
                if comp.ingredient:
                    await self.repo.log_intake(
                        user_id=user_id,
                        food_id=comp.ingredient.id,
                        quantity=effective_qty,
                        unit=comp.unit,
                        day=day,
                        source=source,
                    )
                    created_entries.append(
                        {
                            "ingredient_id": comp.ingredient.id,
                            "ingredient_name": comp.ingredient.name,
                            "quantity": effective_qty,
                            "unit": comp.unit,
                            "source": source.value,
                        }
                    )
                elif comp.child_recipe:
                    await _expand(comp.child_recipe, effective_qty)

        await _expand(recipe, servings)
        await self.session.flush()
        return {"recipe_id": recipe.id, "created_entries": created_entries}
