from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import (
    NUTRIENT_DEFINITIONS,
    DEFAULT_GOAL_BY_SLUG,
    NutritionGoal,
    NutritionNutrient,
    NutrientScalingRule,
    ScalingRuleType,
    UserNutrientScalingRule,
    goal_column,
    multiplier_column,
)


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

    async def fetch_goal_snapshot(self, user_id: int) -> NutritionGoal | None:
        stmt = select(NutritionGoal).where(NutritionGoal.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_goal_snapshot(
        self,
        user_id: int,
        goal_values: dict[str, float | None],
        *,
        computed_from_date,
        computed_at: datetime,
        calorie_source: str | None,
    ) -> NutritionGoal:
        goal = await self.fetch_goal_snapshot(user_id)
        if goal is None:
            goal = NutritionGoal(user_id=user_id)
            self.session.add(goal)

        for definition in NUTRIENT_DEFINITIONS:
            column = goal_column(definition.slug)
            value = goal_values.get(definition.slug)
            setattr(goal, column, value)

        goal.calorie_source = calorie_source
        goal.computed_from_date = computed_from_date
        goal.computed_at = computed_at
        return goal

    async def list_scaling_rules(self) -> list[NutrientScalingRule]:
        stmt = select(NutrientScalingRule).order_by(NutrientScalingRule.id.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_user_rules(self, user_id: int) -> list[NutrientScalingRule]:
        stmt = (
            select(NutrientScalingRule)
            .join(UserNutrientScalingRule)
            .where(UserNutrientScalingRule.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def assign_rule(self, user_id: int, rule_id: int) -> UserNutrientScalingRule:
        stmt = select(UserNutrientScalingRule).where(
            UserNutrientScalingRule.user_id == user_id,
            UserNutrientScalingRule.rule_id == rule_id,
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            record = UserNutrientScalingRule(user_id=user_id, rule_id=rule_id)
            self.session.add(record)
        return record

    async def remove_rules(self, user_id: int, rule_ids: Iterable[int]) -> None:
        stmt = (
            delete(UserNutrientScalingRule)
            .where(UserNutrientScalingRule.user_id == user_id)
            .where(UserNutrientScalingRule.rule_id.in_(list(rule_ids)))
        )
        await self.session.execute(stmt)

    async def get_rule_by_slug(self, slug: str) -> NutrientScalingRule | None:
        stmt = select(NutrientScalingRule).where(NutrientScalingRule.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_manual_rule(self, user_id: int) -> NutrientScalingRule | None:
        stmt = select(NutrientScalingRule).where(
            NutrientScalingRule.owner_user_id == user_id,
            NutrientScalingRule.type == ScalingRuleType.MANUAL,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_manual_rule(
        self, user_id: int, multipliers: dict[str, float]
    ) -> NutrientScalingRule:
        rule = await self.get_manual_rule(user_id)
        created = False
        if rule is None:
            rule = NutrientScalingRule(
                slug=f"user-{user_id}-manual",
                label="Manual",
                description="Manual nutrient adjustments",
                type=ScalingRuleType.MANUAL,
                owner_user_id=user_id,
            )
            self.session.add(rule)
            created = True

        for definition in NUTRIENT_DEFINITIONS:
            column = multiplier_column(definition.slug)
            if definition.slug == "calories":
                setattr(rule, column, 1.0)
                continue
            value = multipliers.get(definition.slug, getattr(rule, column, 1.0))
            setattr(rule, column, value)
        if created:
            await self.session.flush()
        return rule

    async def ensure_manual_rule_assigned(self, user_id: int) -> NutrientScalingRule:
        rule = await self.get_manual_rule(user_id)
        if rule is None:
            rule = await self.upsert_manual_rule(user_id, {})
        if rule.id is None:
            await self.session.flush()
        await self.assign_rule(user_id, int(rule.id))
        return rule

    async def baseline_goal_map(self) -> dict[str, float]:
        return DEFAULT_GOAL_BY_SLUG.copy()
