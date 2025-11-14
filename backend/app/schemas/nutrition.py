from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class NutrientDefinitionResponse(BaseModel):
    slug: str
    display_name: str
    category: str
    group: str
    unit: str
    default_goal: float


class NutritionFoodPayload(BaseModel):
    name: str
    default_unit: str = Field(default="serving")
    source: str | None = None
    status: str | None = None
    nutrients: dict[str, float | None]


class NutritionFoodResponse(BaseModel):
    id: int
    name: str
    default_unit: str
    status: str
    source: str | None
    nutrients: dict[str, float | None]


class NutrientGoalItem(BaseModel):
    slug: str
    display_name: str
    unit: str
    category: str
    group: str
    goal: float
    default_goal: float
    computed_at: datetime | None = None
    computed_from_date: date | None = None
    calorie_source: str | None = None


class NutrientGoalUpdateRequest(BaseModel):
    goal: float = Field(gt=0)


class NutrientProgress(BaseModel):
    slug: str
    display_name: str
    group: str
    unit: str
    amount: float | None = None
    goal: float | None = None
    percent_of_goal: float | None = None


class NutritionDailySummaryResponse(BaseModel):
    date: date
    nutrients: list[NutrientProgress]


class NutritionHistoryResponse(BaseModel):
    window_days: int
    nutrients: list[NutrientProgress]


class LogIntakeRequest(BaseModel):
    food_id: int
    quantity: float = Field(gt=0)
    unit: str
    day: date | None = None


class ClaudeMessageRequest(BaseModel):
    session_id: str | None = None
    message: str


class ClaudeMessageResponse(BaseModel):
    session_id: str
    reply: str
    logged_entries: list[dict[str, Any]]


class NutritionIntakeEntry(BaseModel):
    id: int
    food_id: int
    food_name: str | None = None
    quantity: float
    unit: str
    source: str


class NutritionIntakeMenuResponse(BaseModel):
    day: date
    entries: list[NutritionIntakeEntry]


class NutritionIntakeUpdateRequest(BaseModel):
    quantity: float = Field(gt=0)
    unit: str


class ScalingRuleItem(BaseModel):
    slug: str
    label: str
    description: str | None = None
    type: str
    owner_user_id: int | None = None
    active: bool
    multipliers: dict[str, float]


class ScalingRuleListResponse(BaseModel):
    rules: list[ScalingRuleItem]
    manual_rule_slug: str | None = None
