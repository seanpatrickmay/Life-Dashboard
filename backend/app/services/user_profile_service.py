from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import (
    DailyEnergy,
    PreferredUnits,
    UserMeasurement,
    UserProfile,
)
from app.db.repositories.nutrition_goals_repository import NutritionGoalsRepository
from app.services.nutrition_goals_service import NutritionGoalsService
from app.utils.timezone import eastern_now


class UserProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.goals_repo = NutritionGoalsRepository(session)
        self.goals_service = NutritionGoalsService(session)

    async def get_profile(self, user_id: int) -> UserProfile:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await self.session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.session.add(profile)
            await self.session.flush()
        return profile

    async def fetch_profile_payload(self, user_id: int) -> dict[str, Any]:
        profile = await self.get_profile(user_id)
        measurements = await self._recent_measurements(user_id)
        latest_energy = await self._latest_energy(user_id)
        goals = await self.goals_service.list_goals(user_id)
        scaling_rules = await self.goals_service.list_scaling_rules(user_id)
        return {
            "profile": {
                "date_of_birth": profile.date_of_birth,
                "sex": profile.sex,
                "height_cm": profile.height_cm,
                "current_weight_kg": profile.current_weight_kg,
                "preferred_units": profile.preferred_units.value,
                "daily_energy_delta_kcal": profile.daily_energy_delta_kcal,
            },
            "measurements": measurements,
            "latest_energy": latest_energy,
            "goals": goals,
            "scaling_rules": scaling_rules,
        }

    async def update_profile(self, user_id: int, updates: dict[str, Any]) -> UserProfile:
        profile = await self.get_profile(user_id)
        allowed_fields = {
            "date_of_birth",
            "sex",
            "height_cm",
            "current_weight_kg",
            "preferred_units",
            "daily_energy_delta_kcal",
        }
        weight_before = profile.current_weight_kg
        for key, value in updates.items():
            if key not in allowed_fields:
                continue
            if key == "preferred_units" and value:
                value = PreferredUnits(value)
            if key in {"height_cm", "current_weight_kg"}:
                if value in (None, ""):
                    value = None
                elif value is not None:
                    value = float(value)
            if key == "daily_energy_delta_kcal":
                if value in (None, ""):
                    value = 0
                else:
                    value = int(value)
            setattr(profile, key, value)

        if (
            profile.current_weight_kg
            and profile.current_weight_kg != weight_before
        ):
            measurement = UserMeasurement(
                user_id=user_id,
                measured_at=eastern_now(),
                weight_kg=profile.current_weight_kg,
            )
            self.session.add(measurement)
        await self.session.flush()
        await self.goals_service.recompute_goals(user_id)
        return profile

    async def _recent_measurements(self, user_id: int) -> list[dict[str, Any]]:
        stmt = (
            select(UserMeasurement)
            .where(UserMeasurement.user_id == user_id)
            .order_by(UserMeasurement.measured_at.desc())
            .limit(30)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [
            {"measured_at": row.measured_at, "weight_kg": row.weight_kg}
            for row in rows
        ]

    async def _latest_energy(self, user_id: int) -> dict[str, Any] | None:
        stmt = (
            select(DailyEnergy)
            .where(DailyEnergy.user_id == user_id)
            .order_by(DailyEnergy.metric_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        entry = result.scalar_one_or_none()
        if entry is None:
            return None
        return {
            "metric_date": entry.metric_date,
            "active_kcal": entry.active_kcal,
            "bmr_kcal": entry.bmr_kcal,
            "total_kcal": entry.total_kcal,
            "source": entry.source,
        }
