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


def _require_live_llm() -> None:
    """Skip this test unless RUN_LIVE_LLM_TESTS=1 is set in the environment."""
    import os
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to run live LLM evaluations.")


# ── Layer 2: AI Extraction Accuracy ──
# These tests call the REAL _extract_food_mentions with a live LLM.
# Mark @pytest.mark.live_llm so they only run when explicitly opted in.

class TestAIExtraction:
    """Verify the AI correctly extracts foods from natural language (live LLM)."""

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_simple_food_extraction(self):
        """'I had 2 eggs' should extract eggs with qty ~2."""
        _require_live_llm()
        from app.services.claude_nutrition_agent import NutritionAssistantAgent

        session = AsyncMock()
        agent = NutritionAssistantAgent(session)
        # Call the REAL extraction method (hits OpenAI)
        result = await agent._extract_food_mentions("I had 2 eggs")

        assert len(result["foods"]) >= 1
        egg_item = next((f for f in result["foods"] if "egg" in f["name"].lower()), None)
        assert egg_item is not None, f"Expected 'egg' in foods, got: {result['foods']}"
        assert egg_item["quantity"] == pytest.approx(2, abs=0.5)

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_multi_food_extraction(self):
        """'chicken salad and a banana' should extract 2 items."""
        _require_live_llm()
        from app.services.claude_nutrition_agent import NutritionAssistantAgent

        session = AsyncMock()
        agent = NutritionAssistantAgent(session)
        result = await agent._extract_food_mentions("I ate a chicken salad and a banana")

        assert len(result["foods"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_quantity_with_units(self):
        """'a cup of Greek yogurt' should extract qty ~1, unit containing 'cup'."""
        _require_live_llm()
        from app.services.claude_nutrition_agent import NutritionAssistantAgent

        session = AsyncMock()
        agent = NutritionAssistantAgent(session)
        result = await agent._extract_food_mentions("I had a cup of Greek yogurt")

        assert len(result["foods"]) >= 1
        yogurt = result["foods"][0]
        assert yogurt["quantity"] == pytest.approx(1, abs=0.5)
        assert "cup" in yogurt["unit"].lower()

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_supplements_extraction(self):
        """'took vitamin D and fish oil' should extract 2 supplement items."""
        _require_live_llm()
        from app.services.claude_nutrition_agent import NutritionAssistantAgent

        session = AsyncMock()
        agent = NutritionAssistantAgent(session)
        result = await agent._extract_food_mentions("I took vitamin D and fish oil this morning")

        assert len(result["foods"]) >= 2


# ── Layer 3: End-to-End Calorie Pipeline ──
# Combines mocked extraction (for determinism) with real _accumulate + daily_summary.

class TestEndToEndCalories:
    """Verify extraction -> logging -> daily_summary produces correct calorie totals."""

    @pytest.mark.asyncio
    async def test_known_ingredient_through_daily_summary(self):
        """
        Mock extraction to return 3 eggs.
        Build intake records with known calorie profiles.
        Run daily_summary and assert calories = 216.
        """
        session = AsyncMock()
        service = NutritionIntakeService(session)

        # Build realistic intake objects with proper nutrient profiles
        egg_intakes = [
            _make_intake("Egg", quantity=3.0, unit="piece", calories=72.0, protein=6.0, fat=5.0),
        ]

        service.repo.fetch_for_date = AsyncMock(return_value=egg_intakes)
        service.goals_service.list_goals = AsyncMock(return_value=[
            {"slug": "calories", "goal": 2000.0, "display_name": "Calories", "unit": "kcal"},
            {"slug": "protein", "goal": 160.0, "display_name": "Protein", "unit": "g"},
        ])

        summary = await service.daily_summary(user_id=1, day=date(2026, 3, 19))
        cal = next(n for n in summary["nutrients"] if n["slug"] == "calories")
        protein = next(n for n in summary["nutrients"] if n["slug"] == "protein")

        assert cal["amount"] == pytest.approx(216.0)  # 3 * 72
        assert protein["amount"] == pytest.approx(18.0)  # 3 * 6

    @pytest.mark.asyncio
    async def test_mixed_meal_calorie_total(self):
        """
        2 eggs (72 each) + 1 toast (80) + 1 cup yogurt (150) = 374 kcal.
        """
        session = AsyncMock()
        service = NutritionIntakeService(session)

        intakes = [
            _make_intake("Egg", quantity=2.0, unit="piece", calories=72.0),
            _make_intake("Toast", quantity=1.0, unit="slice", calories=80.0),
            _make_intake("Greek yogurt", quantity=1.0, unit="cup", calories=150.0),
        ]

        service.repo.fetch_for_date = AsyncMock(return_value=intakes)
        service.goals_service.list_goals = AsyncMock(return_value=[
            {"slug": "calories", "goal": 2000.0, "display_name": "Calories", "unit": "kcal"},
        ])

        summary = await service.daily_summary(user_id=1, day=date(2026, 3, 19))
        cal = next(n for n in summary["nutrients"] if n["slug"] == "calories")
        assert cal["amount"] == pytest.approx(374.0)
        assert cal["percent_of_goal"] == pytest.approx(18.7)  # 374/2000*100
