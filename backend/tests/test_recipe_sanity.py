"""Tests for recipe ingredient quantity sanity — no 150 cups of flour."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest

from app.core.config import get_settings
get_settings.cache_clear()

from app.services.claude_nutrition_agent import NutritionAssistantAgent


# ── Unit Tests: _clamp_per_serving_qty ──


class TestClampPerServingQty:
    """Verify the sanity clamp catches absurd ingredient quantities."""

    def test_reasonable_flour_passes_through(self):
        """0.2 cups flour for 1 serving is fine."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(0.2, 1.0, "cup")
        assert result == pytest.approx(0.2)

    def test_absurd_flour_is_clamped(self):
        """150 cups flour for 1 serving should be clamped to 6 cups."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(150.0, 1.0, "cup")
        assert result == pytest.approx(6.0)

    def test_batch_flour_reasonable(self):
        """2.5 cups flour for 12 servings = 0.21 per serving — fine."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(2.5, 12.0, "cup")
        assert result == pytest.approx(2.5)

    def test_batch_flour_absurd(self):
        """60 cups flour for 12 servings = 5 per serving — fine (limit is 6)."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(60.0, 12.0, "cup")
        assert result == pytest.approx(60.0)

    def test_weight_grams_reasonable(self):
        """30g butter for 1 serving is fine."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(30.0, 1.0, "g")
        assert result == pytest.approx(30.0)

    def test_weight_grams_absurd(self):
        """5000g butter for 1 serving should be clamped to 1000g."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(5000.0, 1.0, "g")
        assert result == pytest.approx(1000.0)

    def test_tbsp_reasonable(self):
        """2 tbsp sugar for 1 serving is fine."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(2.0, 1.0, "tbsp")
        assert result == pytest.approx(2.0)

    def test_tbsp_absurd(self):
        """50 tbsp sugar for 1 serving should be clamped to 8."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(50.0, 1.0, "tbsp")
        assert result == pytest.approx(8.0)

    def test_piece_unit_reasonable(self):
        """2 eggs for 1 serving is fine."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(2.0, 1.0, "piece")
        assert result == pytest.approx(2.0)

    def test_piece_unit_absurd(self):
        """30 eggs for 1 serving should be clamped to 10."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(30.0, 1.0, "piece")
        assert result == pytest.approx(10.0)

    def test_zero_servings_treated_as_one(self):
        """If servings=0, treat as 1 to avoid division by zero."""
        result = NutritionAssistantAgent._clamp_per_serving_qty(150.0, 0.0, "cup")
        assert result == pytest.approx(6.0)


# ── Live LLM Tests: Recipe Suggestion Sanity ──


def _require_live_llm() -> None:
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to run live LLM tests.")


class TestRecipeSuggestionLive:
    """Verify the LLM produces realistic ingredient quantities for common foods."""

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_coffee_roll_flour_reasonable(self):
        """A Dunkin coffee roll should have realistic flour per serving."""
        _require_live_llm()
        session = AsyncMock()
        agent = NutritionAssistantAgent(session)
        suggestion = await agent._suggest_recipe("Dunkin coffee roll")

        assert suggestion is not None
        servings = suggestion["recipe"]["servings"]
        assert servings >= 1, f"servings should be >= 1, got {servings}"

        flour_items = [
            i for i in suggestion["ingredients"]
            if "flour" in i["name"].lower()
        ]
        for item in flour_items:
            per_serving = item["quantity"] / servings
            unit = item["unit"].lower()
            # 100g or ~0.75 cups is max reasonable flour for one pastry
            if unit in ("g", "gram", "grams"):
                assert per_serving < 120, (
                    f"Flour per serving too high: {per_serving:.0f}g"
                )
            elif unit in ("cup", "cups"):
                assert per_serving < 1.0, (
                    f"Flour per serving too high: {per_serving:.2f} cups"
                )

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_iced_latte_milk_reasonable(self):
        """A large iced latte should have realistic milk per serving."""
        _require_live_llm()
        session = AsyncMock()
        agent = NutritionAssistantAgent(session)
        suggestion = await agent._suggest_recipe("large iced latte")

        assert suggestion is not None
        servings = suggestion["recipe"]["servings"]

        milk_items = [
            i for i in suggestion["ingredients"]
            if "milk" in i["name"].lower()
        ]
        for item in milk_items:
            per_serving = item["quantity"] / servings
            unit = item["unit"].lower()
            # A large latte is ~16-24 fl oz, or ~2-3 cups, or ~500-700ml
            if unit in ("fl oz", "oz", "ounce"):
                assert per_serving <= 24, (
                    f"Milk per serving too high: {per_serving:.0f} {unit}"
                )
            elif unit in ("cup", "cups"):
                assert per_serving <= 3.0, (
                    f"Milk per serving too high: {per_serving:.2f} cups"
                )
            elif unit in ("ml", "milliliter"):
                assert per_serving <= 750, (
                    f"Milk per serving too high: {per_serving:.0f}ml"
                )

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_sandwich_bread_reasonable(self):
        """A sandwich should not have more than a few slices of bread."""
        _require_live_llm()
        session = AsyncMock()
        agent = NutritionAssistantAgent(session)
        suggestion = await agent._suggest_recipe("turkey sandwich")

        assert suggestion is not None
        servings = suggestion["recipe"]["servings"]

        bread_items = [
            i for i in suggestion["ingredients"]
            if "bread" in i["name"].lower()
        ]
        for item in bread_items:
            per_serving = item["quantity"] / servings
            assert per_serving <= 4, (
                f"Bread per serving too high: {item['quantity']} {item['unit']} / "
                f"{servings} servings = {per_serving:.2f} per serving"
            )

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_burrito_no_absurd_quantities(self):
        """No ingredient in a burrito should exceed sanity limits per serving."""
        _require_live_llm()
        session = AsyncMock()
        agent = NutritionAssistantAgent(session)
        suggestion = await agent._suggest_recipe("chicken burrito from Chipotle")

        assert suggestion is not None
        servings = suggestion["recipe"]["servings"]

        for item in suggestion["ingredients"]:
            per_serving = item["quantity"] / servings
            unit = item["unit"].lower()
            if unit in ("cup", "cups"):
                assert per_serving <= 3, (
                    f"{item['name']}: {per_serving:.2f} cups per serving is too high"
                )
            elif unit in ("g", "gram", "grams"):
                assert per_serving <= 400, (
                    f"{item['name']}: {per_serving:.0f}g per serving is too high"
                )
