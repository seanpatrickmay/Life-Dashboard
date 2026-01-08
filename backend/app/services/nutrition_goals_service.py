from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import (
    DEFAULT_GOAL_BY_SLUG,
    NUTRIENT_DEFINITIONS,
    NutritionGoal,
    ScalingRuleType,
    goal_column,
    multiplier_column,
)
from app.db.repositories.nutrition_goals_repository import NutritionGoalsRepository
from app.services.nutrition_goal_engine import NutritionGoalEngine
from app.utils.timezone import eastern_now


class NutritionGoalsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NutritionGoalsRepository(session)
        self.engine = NutritionGoalEngine(session, self.repo)

    async def list_goals(self, user_id: int) -> list[dict]:
        nutrients = await self.repo.list_nutrients()
        if not nutrients:
            nutrients = list(NUTRIENT_DEFINITIONS)
        snapshot = await self.repo.fetch_goal_snapshot(user_id)
        if snapshot is None:
            snapshot = await self.recompute_goals(user_id)
        computed_at = snapshot.computed_at if snapshot else None
        computed_from_date = snapshot.computed_from_date if snapshot else None
        calorie_source = snapshot.calorie_source if snapshot else None

        items: list[dict] = []
        for nutrient in nutrients:
            column = goal_column(nutrient.slug)
            value = getattr(snapshot, column, None) if snapshot else None
            goal_value = value if value is not None else nutrient.default_goal
            items.append(
                {
                    "slug": nutrient.slug,
                    "display_name": nutrient.display_name,
                    "unit": nutrient.unit,
                    "category": nutrient.category.value,
                    "group": nutrient.group.value,
                    "goal": goal_value,
                    "default_goal": nutrient.default_goal,
                    "computed_at": computed_at,
                    "computed_from_date": computed_from_date,
                    "calorie_source": calorie_source,
                }
            )
        return items

    async def recompute_goals(self, user_id: int) -> NutritionGoal:
        result = await self.engine.compute(user_id, include_manual=True)
        snapshot = await self.repo.upsert_goal_snapshot(
            user_id,
            result.final,
            computed_from_date=result.source_date,
            computed_at=eastern_now(),
            calorie_source=result.calorie_source,
        )
        await self.session.flush()
        return snapshot

    async def update_goal(self, user_id: int, slug: str, target_value: float) -> dict:
        if target_value <= 0:
            raise ValueError("Goal must be positive")

        baseline_result = await self.engine.compute(user_id, include_manual=False)
        baseline_value = baseline_result.final.get(slug)
        if baseline_value is None or baseline_value == 0:
            raise ValueError("Unable to adjust goal without a baseline value")
        multiplier = target_value / baseline_value

        await self.repo.ensure_manual_rule_assigned(user_id)
        await self.repo.upsert_manual_rule(user_id, {slug: multiplier})
        await self.recompute_goals(user_id)
        goals = await self.list_goals(user_id)
        for goal in goals:
            if goal["slug"] == slug:
                return goal
        raise ValueError("Goal not found")

    async def list_scaling_rules(self, user_id: int) -> dict:
        assignments = await self.repo.list_user_rules(user_id)
        assigned_ids = {rule.id for rule in assignments if rule.id is not None}
        manual_rule = await self.repo.get_manual_rule(user_id)

        rules = await self.repo.list_scaling_rules()
        response: list[dict] = []
        for rule in rules:
            if rule.type == ScalingRuleType.MANUAL and rule.owner_user_id != user_id:
                continue
            multipliers = {
                definition.slug: getattr(rule, multiplier_column(definition.slug), 1.0)
                for definition in NUTRIENT_DEFINITIONS
            }
            response.append(
                {
                    "slug": rule.slug,
                    "label": rule.label,
                    "description": rule.description,
                    "type": rule.type.value,
                    "owner_user_id": rule.owner_user_id,
                    "active": bool(rule.id in assigned_ids),
                    "multipliers": multipliers,
                }
            )

        return {"rules": response, "manual_rule_slug": manual_rule.slug if manual_rule else None}

    async def set_rule_state(self, user_id: int, slug: str, enabled: bool) -> None:
        rule = await self.repo.get_rule_by_slug(slug)
        if rule is None:
            raise ValueError("Unknown rule")
        if rule.type == ScalingRuleType.MANUAL:
            raise ValueError("Manual rule state is managed via goal updates")

        if rule.id is None:
            await self.session.flush()
        if enabled:
            await self.repo.assign_rule(user_id, int(rule.id))
        else:
            await self.repo.remove_rules(user_id, [int(rule.id)])
        await self.recompute_goals(user_id)
