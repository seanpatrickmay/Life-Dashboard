"""
Three-layer test harness for food logging accuracy.
Layer 1: Nutrient math (deterministic) — tests _accumulate and daily_summary
Layer 2: AI extraction accuracy (requires LLM) — added in Task 9
Layer 3: End-to-end calorie pipeline (requires LLM) — added in Task 9
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.nutrition import (
    NUTRIENT_DEFINITIONS,
    NutritionIngredient,
    NutritionIngredientProfile,
    NutritionIntake,
    NutritionIntakeSource,
)
from app.services.nutrition_intake_service import NutritionIntakeService


# ── Helpers ──

def _make_intake(ingredient_name: str, quantity: float, unit: str, calories: float, protein: float = 0, carbs: float = 0, fat: float = 0) -> MagicMock:
    """Build a mock NutritionIntake with an attached profile containing known nutrient values."""
    profile = MagicMock(spec=NutritionIngredientProfile)
    # Set all nutrient columns to 0 by default
    for defn in NUTRIENT_DEFINITIONS:
        setattr(profile, defn.column_name, 0.0)
    # Override the ones we care about (use actual column names from NUTRIENT_DEFINITIONS)
    profile.calories_kcal = calories
    profile.protein_g = protein
    profile.carbohydrates_g = carbs
    profile.fat_g = fat

    ingredient = MagicMock(spec=NutritionIngredient)
    ingredient.name = ingredient_name
    ingredient.profile = profile

    intake = MagicMock(spec=NutritionIntake)
    intake.ingredient = ingredient
    intake.quantity = quantity
    intake.unit = unit
    return intake


# ── Layer 1: Nutrient Math ──


class TestNutrientMath:
    """Verify _accumulate computes correct calorie/macro totals from intake records."""

    def test_single_ingredient_calories(self):
        """2 eggs at 72 kcal/piece = 144 kcal total."""
        service = NutritionIntakeService.__new__(NutritionIntakeService)
        intakes = [_make_intake("Egg", quantity=2.0, unit="piece", calories=72.0, protein=6.0, fat=5.0)]
        totals = service._accumulate(intakes)
        assert totals["calories"] == pytest.approx(144.0)
        assert totals["protein"] == pytest.approx(12.0)
        assert totals["fat"] == pytest.approx(10.0)

    def test_multiple_ingredients_sum(self):
        """2 eggs (72 each) + 1 toast (80) = 224 kcal."""
        service = NutritionIntakeService.__new__(NutritionIntakeService)
        intakes = [
            _make_intake("Egg", quantity=2.0, unit="piece", calories=72.0),
            _make_intake("Toast", quantity=1.0, unit="slice", calories=80.0),
        ]
        totals = service._accumulate(intakes)
        assert totals["calories"] == pytest.approx(224.0)

    def test_fractional_quantity(self):
        """0.5 cups of yogurt at 150 kcal/cup = 75 kcal."""
        service = NutritionIntakeService.__new__(NutritionIntakeService)
        intakes = [_make_intake("Greek yogurt", quantity=0.5, unit="cup", calories=150.0, protein=15.0)]
        totals = service._accumulate(intakes)
        assert totals["calories"] == pytest.approx(75.0)
        assert totals["protein"] == pytest.approx(7.5)

    def test_zero_quantity_yields_zero(self):
        """Edge case: 0 quantity should yield 0 calories."""
        service = NutritionIntakeService.__new__(NutritionIntakeService)
        intakes = [_make_intake("Egg", quantity=0.0, unit="piece", calories=72.0)]
        totals = service._accumulate(intakes)
        assert totals["calories"] == pytest.approx(0.0)

    def test_empty_intakes(self):
        """No intakes should yield all-zero totals."""
        service = NutritionIntakeService.__new__(NutritionIntakeService)
        totals = service._accumulate([])
        assert totals["calories"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_daily_summary_calorie_total(self):
        """daily_summary should return correct calorie amount and percent_of_goal."""
        session = AsyncMock()
        service = NutritionIntakeService(session)

        intakes = [
            _make_intake("Egg", quantity=3.0, unit="piece", calories=72.0),
        ]
        service.repo.fetch_for_date = AsyncMock(return_value=intakes)
        service.goals_service.list_goals = AsyncMock(return_value=[
            {"slug": "calories", "goal": 2000.0, "display_name": "Calories", "unit": "kcal"},
        ])

        summary = await service.daily_summary(user_id=1, day=date(2026, 3, 19))
        cal_entry = next(n for n in summary["nutrients"] if n["slug"] == "calories")
        assert cal_entry["amount"] == pytest.approx(216.0)  # 3 * 72
        assert cal_entry["percent_of_goal"] == pytest.approx(10.8)  # 216/2000*100

    @pytest.mark.asyncio
    async def test_ingredient_not_found_raises(self):
        """Logging a non-existent ingredient should raise ValueError."""
        session = AsyncMock()
        service = NutritionIntakeService(session)
        service.ingredients_repo.get_ingredient = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Ingredient not found"):
            await service.log_manual_intake(
                user_id=1, ingredient_id=999, quantity=1.0, unit="piece",
                day=date(2026, 3, 19),
            )
