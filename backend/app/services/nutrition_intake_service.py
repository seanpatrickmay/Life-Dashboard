from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import (
    NUTRIENT_DEFINITIONS,
    NutritionIntake,
    NutritionIntakeSource,
)
from app.db.repositories.nutrition_intake_repository import NutritionIntakeRepository
from app.db.repositories.nutrition_foods_repository import NutritionFoodsRepository
from app.services.nutrition_goals_service import NutritionGoalsService
from app.utils.timezone import eastern_today


class NutritionIntakeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NutritionIntakeRepository(session)
        self.food_repo = NutritionFoodsRepository(session)
        self.goals_service = NutritionGoalsService(session)

    async def log_manual_intake(
        self,
        *,
        user_id: int,
        food_id: int,
        quantity: float,
        unit: str,
        day: date,
    ) -> dict[str, Any]:
        food = await self.food_repo.get_food(food_id)
        if food is None:
            raise ValueError("Food not found")
        intake = await self.repo.log_intake(
            user_id=user_id,
            food_id=food_id,
            quantity=quantity,
            unit=unit,
            day=day,
            source=NutritionIntakeSource.MANUAL,
        )
        await self.session.flush()
        await self.session.commit()
        return {
            "id": intake.id,
            "food_id": food_id,
            "day": day,
            "quantity": quantity,
            "unit": unit,
        }

    async def list_day_menu(self, user_id: int, day: date) -> list[dict[str, Any]]:
        intakes = await self.repo.fetch_for_day_with_food(user_id, day)
        return [self._serialize_entry(intake) for intake in intakes]

    async def update_intake(
        self, intake_id: int, *, quantity: float, unit: str
    ) -> dict[str, Any]:
        intake = await self.repo.update_quantity(intake_id, quantity=quantity, unit=unit)
        if intake is None:
            raise ValueError("Intake not found")
        await self.session.flush()
        await self.session.commit()
        return self._serialize_entry(intake)

    async def delete_intake(self, intake_id: int) -> None:
        await self.repo.delete_intake(intake_id)
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
            profile = intake.food.profile
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
            profile = intake.food.profile
            for definition in NUTRIENT_DEFINITIONS:
                value = getattr(profile, definition.column_name)
                if value is None:
                    continue
                totals[definition.slug] += value * intake.quantity
        return totals

    def _serialize_entry(self, intake: NutritionIntake) -> dict[str, Any]:
        return {
            "id": intake.id,
            "food_id": intake.food_id,
            "food_name": intake.food.name if intake.food else None,
            "quantity": intake.quantity,
            "unit": intake.unit,
            "source": intake.source.value,
        }
