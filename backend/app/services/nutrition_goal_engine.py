from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import DailyEnergy, UserProfile
from app.db.models.nutrition import (
    DEFAULT_GOAL_BY_SLUG,
    NUTRIENT_DEFINITIONS,
    NutrientScalingRule,
    ScalingRuleType,
    goal_column,
    multiplier_column,
)
from app.db.repositories.nutrition_goals_repository import NutritionGoalsRepository
from app.utils.timezone import eastern_today


@dataclass
class GoalComputationResult:
    baseline: dict[str, float]
    final: dict[str, float]
    calorie_source: str | None
    source_date: date | None


class NutritionGoalEngine:
    def __init__(
        self,
        session: AsyncSession,
        repo: NutritionGoalsRepository,
    ) -> None:
        self.session = session
        self.repo = repo

    async def compute(
        self, user_id: int, *, include_manual: bool = True
    ) -> GoalComputationResult:
        profile = await self._get_or_create_profile(user_id)
        target_day = eastern_today() - timedelta(days=1)
        energy_entry = await self._energy_for_day(user_id, target_day)

        if energy_entry and energy_entry.total_kcal:
            total_kcal = energy_entry.total_kcal
            calorie_source = "garmin"
            source_date = target_day
        else:
            total_kcal = self._estimate_total_calories(profile)
            calorie_source = "calculated"
            source_date = target_day

        total_kcal += profile.daily_energy_delta_kcal or 0
        total_kcal = max(total_kcal, 1200)

        baseline = self._build_baseline_map(total_kcal, profile)
        multipliers = await self._collect_multipliers(user_id, include_manual=include_manual)
        final = {
            slug: max(baseline[slug] * multipliers.get(slug, 1.0), 0.0)
            for slug in baseline
        }
        return GoalComputationResult(
            baseline=baseline,
            final=final,
            calorie_source=calorie_source,
            source_date=source_date,
        )

    async def _get_or_create_profile(self, user_id: int) -> UserProfile:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.session.add(profile)
            await self.session.flush()
        return profile

    async def _energy_for_day(self, user_id: int, target_day: date) -> DailyEnergy | None:
        stmt = (
            select(DailyEnergy)
            .where(
                DailyEnergy.user_id == user_id,
                DailyEnergy.metric_date == target_day,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _estimate_total_calories(self, profile: UserProfile) -> float:
        weight = profile.current_weight_kg or 72.0
        height = profile.height_cm or 175.0
        age_years = self._estimate_age(profile.date_of_birth)
        sex = (profile.sex or "").lower()
        base = 10 * weight + 6.25 * height - 5 * age_years
        if sex.startswith("f"):
            base -= 161
        else:
            base += 5
        activity_factor = 1.45
        return base * activity_factor

    def _estimate_age(self, dob: date | None) -> int:
        if not dob:
            return 34
        today = eastern_today()
        years = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            years -= 1
        return max(years, 18)

    def _build_baseline_map(self, calories: float, profile: UserProfile) -> dict[str, float]:
        values: dict[str, float] = {slug: DEFAULT_GOAL_BY_SLUG[slug] for slug in DEFAULT_GOAL_BY_SLUG}
        values["calories"] = calories

        weight = profile.current_weight_kg or 72.0
        protein = max(weight * 1.6, 80.0)
        fat = max(weight * 0.8, 0.25 * calories / 9.0)
        remaining_calories = max(calories - protein * 4 - fat * 9, calories * 0.25)
        carbs = remaining_calories / 4.0
        fiber = max(25.0, calories / 1000 * 14.0)

        values["protein"] = protein
        values["fat"] = fat
        values["carbohydrates"] = carbs
        values["fiber"] = fiber
        return values

    async def _collect_multipliers(
        self, user_id: int, *, include_manual: bool
    ) -> dict[str, float]:
        rules = await self.repo.list_user_rules(user_id)
        multipliers = {definition.slug: 1.0 for definition in NUTRIENT_DEFINITIONS}
        for rule in rules:
            if rule.type == ScalingRuleType.MANUAL and not include_manual:
                continue
            for definition in NUTRIENT_DEFINITIONS:
                column = multiplier_column(definition.slug)
                value = getattr(rule, column, 1.0) or 1.0
                multipliers[definition.slug] *= value
        return multipliers
