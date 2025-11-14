from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.nutrition import NutrientGoalItem, ScalingRuleListResponse


class UserProfileData(BaseModel):
    date_of_birth: date | None = None
    sex: str | None = None
    height_cm: float | None = Field(default=None, ge=0)
    current_weight_kg: float | None = Field(default=None, ge=0)
    preferred_units: str = "metric"
    daily_energy_delta_kcal: int = 0


class MeasurementItem(BaseModel):
    measured_at: datetime
    weight_kg: float


class DailyEnergySummary(BaseModel):
    metric_date: date
    active_kcal: float | None = None
    bmr_kcal: float | None = None
    total_kcal: float | None = None
    source: str | None = None


class UserProfileResponse(BaseModel):
    profile: UserProfileData
    measurements: list[MeasurementItem]
    latest_energy: DailyEnergySummary | None = None
    goals: list[NutrientGoalItem]
    scaling_rules: ScalingRuleListResponse


class UserProfileUpdateRequest(UserProfileData):
    pass
