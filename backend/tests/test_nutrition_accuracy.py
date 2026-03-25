"""
Full nutrition accuracy test suite.

Layer 1: Nutrient math (deterministic) — tests _accumulate and daily_summary
Layer 2: AI extraction accuracy (requires LLM) — food parsing from natural language
Layer 3: End-to-end calorie pipeline (requires LLM) — recipe → nutrients → totals

Run live tests: RUN_LIVE_LLM_TESTS=1 pytest tests/test_nutrition_accuracy.py -v
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest


def _run(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)

from app.core.config import get_settings
get_settings.cache_clear()

from app.db.models.nutrition import (  # noqa: E402
    NUTRIENT_DEFINITIONS,
    NutritionIngredient,
    NutritionIngredientProfile,
    NutritionIntake,
    NutritionIntakeSource,
)
from app.services.nutrition_intake_service import NutritionIntakeService  # noqa: E402
from app.clients.openai_client import OpenAIResponsesClient  # noqa: E402
from app.prompts import NUTRITION_FOOD_EXTRACTION_PROMPT  # noqa: E402
from app.schemas.llm_outputs import NutritionFoodExtractionOutput  # noqa: E402
from app.services.claude_nutrition_agent import NutritionAssistantAgent  # noqa: E402


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

    def test_daily_summary_calorie_total(self):
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

        summary = _run(service.daily_summary(user_id=1, day=date(2026, 3, 19)))
        cal_entry = next(n for n in summary["nutrients"] if n["slug"] == "calories")
        assert cal_entry["amount"] == pytest.approx(216.0)  # 3 * 72
        assert cal_entry["percent_of_goal"] == pytest.approx(10.8)  # 216/2000*100

    def test_ingredient_not_found_raises(self):
        """Logging a non-existent ingredient should raise NotFoundException."""
        from app.core.exceptions import NotFoundException

        session = AsyncMock()
        service = NutritionIntakeService(session)
        service.ingredients_repo.get_ingredient = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException, match="Ingredient not found"):
            _run(service.log_manual_intake(
                user_id=1, ingredient_id=999, quantity=1.0, unit="piece",
                day=date(2026, 3, 19),
            ))


def _require_live_llm() -> None:
    """Skip this test unless RUN_LIVE_LLM_TESTS=1 is set in the environment."""
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to run live LLM evaluations.")


def _make_client() -> OpenAIResponsesClient:
    return OpenAIResponsesClient()


def _make_agent() -> NutritionAssistantAgent:
    return NutritionAssistantAgent(AsyncMock())


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

    def test_known_ingredient_through_daily_summary(self):
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

        summary = _run(service.daily_summary(user_id=1, day=date(2026, 3, 19)))
        cal = next(n for n in summary["nutrients"] if n["slug"] == "calories")
        protein = next(n for n in summary["nutrients"] if n["slug"] == "protein")

        assert cal["amount"] == pytest.approx(216.0)  # 3 * 72
        assert protein["amount"] == pytest.approx(18.0)  # 3 * 6

    def test_mixed_meal_calorie_total(self):
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

        summary = _run(service.daily_summary(user_id=1, day=date(2026, 3, 19)))
        cal = next(n for n in summary["nutrients"] if n["slug"] == "calories")
        assert cal["amount"] == pytest.approx(374.0)
        assert cal["percent_of_goal"] == pytest.approx(18.7)  # 374/2000*100


# ═══════════════════════════════════════════════════════════════════
# Layer 2 Expanded: Food Extraction Accuracy (Live LLM)
# ═══════════════════════════════════════════════════════════════════


class TestFoodExtractionExpandedLive:
    """Comprehensive food extraction tests covering edge cases and real-world inputs."""

    async def _extract(self, text: str) -> dict:
        client = _make_client()
        prompt = NUTRITION_FOOD_EXTRACTION_PROMPT.format(user_text=text)
        result = await client.generate_json(
            prompt, response_model=NutritionFoodExtractionOutput
        )
        return result.data.model_dump()

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_branded_fast_food(self):
        """'A Big Mac and medium fries from McDonald's' should extract both items."""
        _require_live_llm()
        parsed = await self._extract("A Big Mac and medium fries from McDonald's")
        foods = parsed["foods"]
        names_lower = [f["name"].lower() for f in foods]
        assert any("mac" in n or "big mac" in n for n in names_lower), (
            f"No Big Mac found in {names_lower}"
        )
        assert any("fries" in n or "fry" in n for n in names_lower), (
            f"No fries found in {names_lower}"
        )

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_fractional_quantities(self):
        """'Half a cup of rice and a quarter pound burger' should parse fractions."""
        _require_live_llm()
        parsed = await self._extract("Half a cup of rice and a quarter pound burger")
        foods = parsed["foods"]
        rice = next((f for f in foods if "rice" in f["name"].lower()), None)
        assert rice is not None, f"No rice found in {foods}"
        assert rice["quantity"] == pytest.approx(0.5, abs=0.15)

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_no_food_in_text(self):
        """'I went for a run this morning' should extract zero foods."""
        _require_live_llm()
        parsed = await self._extract("I went for a run this morning")
        foods = parsed["foods"]
        assert len(foods) == 0, f"Expected 0 foods, got {foods}"

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_complex_meal_description(self):
        """A longer description should parse all main items."""
        _require_live_llm()
        parsed = await self._extract(
            "For lunch I had a turkey sandwich on whole wheat with lettuce and tomato, "
            "a small bag of chips, and a can of Coke"
        )
        foods = parsed["foods"]
        assert len(foods) >= 2, f"Expected at least 2 foods, got {foods}"
        names_lower = " ".join(f["name"].lower() for f in foods)
        assert "turkey" in names_lower or "sandwich" in names_lower

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_drinks_extraction(self):
        """'I drank a large iced coffee and a glass of orange juice' should find drinks."""
        _require_live_llm()
        parsed = await self._extract(
            "I drank a large iced coffee and a glass of orange juice"
        )
        foods = parsed["foods"]
        assert len(foods) >= 2, f"Expected at least 2 items, got {foods}"
        names_lower = " ".join(f["name"].lower() for f in foods)
        assert "coffee" in names_lower, f"No coffee found in {names_lower}"
        assert "orange" in names_lower or "juice" in names_lower, (
            f"No orange juice found in {names_lower}"
        )

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_numeric_words(self):
        """'three slices of pizza and two beers' should parse word-numbers."""
        _require_live_llm()
        parsed = await self._extract("three slices of pizza and two beers")
        foods = parsed["foods"]
        pizza = next((f for f in foods if "pizza" in f["name"].lower()), None)
        assert pizza is not None, f"No pizza found in {foods}"
        assert pizza["quantity"] == pytest.approx(3.0, abs=0.5)

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_snack_items(self):
        """'A handful of almonds and a protein bar' should extract both."""
        _require_live_llm()
        parsed = await self._extract("A handful of almonds and a protein bar")
        foods = parsed["foods"]
        assert len(foods) >= 2, f"Expected at least 2, got {foods}"


# ═══════════════════════════════════════════════════════════════════
# Layer 4: Nutrient Profile Accuracy (Live LLM)
# ═══════════════════════════════════════════════════════════════════


# Ground truth calorie ranges (per stated unit) from USDA
KNOWN_CALORIE_RANGES = [
    ("large egg", "piece", 60, 90, "~72 kcal per large egg"),
    ("banana", "piece", 80, 130, "~105 kcal per medium banana"),
    ("chicken breast", "100g", 130, 200, "~165 kcal per 100g cooked"),
    ("white rice", "cup", 170, 260, "~206 kcal per cup cooked"),
    ("olive oil", "tbsp", 100, 140, "~119 kcal per tbsp"),
    ("whole milk", "cup", 130, 170, "~149 kcal per cup"),
    ("peanut butter", "tbsp", 80, 110, "~94 kcal per tbsp"),
    ("white bread", "slice", 55, 90, "~67 kcal per slice"),
    ("butter", "tbsp", 85, 115, "~102 kcal per tbsp"),
    ("cheddar cheese", "oz", 100, 130, "~113 kcal per oz"),
]


class TestNutrientProfileAccuracyLive:
    """Verify the LLM returns realistic calorie values for known foods."""

    async def _fetch_profile(self, food_name: str, unit: str) -> dict[str, float | None]:
        """Fetch nutrient profile using the same production code path."""
        agent = _make_agent()
        return await agent._fetch_nutrient_profile(food_name, unit)

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    @pytest.mark.parametrize(
        "food_name,unit,min_cal,max_cal,description",
        KNOWN_CALORIE_RANGES,
        ids=[r[0] for r in KNOWN_CALORIE_RANGES],
    )
    async def test_calorie_in_range(
        self, food_name: str, unit: str, min_cal: float, max_cal: float, description: str
    ):
        """Calorie values should fall within known USDA ranges."""
        _require_live_llm()
        profile = await self._fetch_profile(food_name, unit)
        calories = profile.get("calories")
        assert calories is not None, (
            f"No calorie value returned for {food_name} per {unit}"
        )
        assert min_cal <= calories <= max_cal, (
            f"{food_name} per {unit}: got {calories:.0f} kcal, "
            f"expected {min_cal}-{max_cal} ({description})"
        )

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_macros_sum_to_calories(self):
        """For chicken breast, protein*4 + carbs*4 + fat*9 should ≈ reported calories."""
        _require_live_llm()
        profile = await self._fetch_profile("chicken breast", "100g")
        cal = profile.get("calories")
        protein = profile.get("protein") or 0
        carbs = profile.get("carbohydrates") or 0
        fat = profile.get("fat") or 0

        assert cal is not None
        computed = protein * 4 + carbs * 4 + fat * 9
        assert abs(computed - cal) / cal < 0.25, (
            f"Macro sum ({computed:.0f}) doesn't match calories ({cal:.0f}). "
            f"P={protein:.1f}g, C={carbs:.1f}g, F={fat:.1f}g"
        )

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_olive_oil_high_fat(self):
        """Olive oil should be almost entirely fat."""
        _require_live_llm()
        profile = await self._fetch_profile("olive oil", "tbsp")
        fat = profile.get("fat")
        protein = profile.get("protein") or 0
        carbs = profile.get("carbohydrates") or 0

        assert fat is not None and fat > 10, (
            f"Olive oil should have >10g fat per tbsp, got {fat}"
        )
        assert protein < 1 and carbs < 1, (
            f"Olive oil should have negligible protein ({protein}) and carbs ({carbs})"
        )

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_egg_protein_content(self):
        """A large egg should have ~6g protein."""
        _require_live_llm()
        profile = await self._fetch_profile("large egg", "piece")
        protein = profile.get("protein")
        assert protein is not None
        assert 4 <= protein <= 9, f"Egg protein should be ~6g, got {protein:.1f}g"

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_banana_carbs_dominant(self):
        """A banana should be mostly carbohydrates, low fat."""
        _require_live_llm()
        profile = await self._fetch_profile("banana", "piece")
        carbs = profile.get("carbohydrates") or 0
        fat = profile.get("fat") or 0
        assert carbs > 20, f"Banana should have >20g carbs, got {carbs:.1f}g"
        assert fat < 2, f"Banana should have <2g fat, got {fat:.1f}g"

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    async def test_chicken_breast_high_protein(self):
        """100g chicken breast should be high protein, low carb."""
        _require_live_llm()
        profile = await self._fetch_profile("chicken breast", "100g")
        protein = profile.get("protein") or 0
        carbs = profile.get("carbohydrates") or 0
        assert protein > 25, f"Chicken should have >25g protein per 100g, got {protein:.1f}g"
        assert carbs < 5, f"Chicken should have <5g carbs per 100g, got {carbs:.1f}g"


# ═══════════════════════════════════════════════════════════════════
# Layer 5: End-to-End Recipe → Nutrient → Total Calories (Live LLM)
# ═══════════════════════════════════════════════════════════════════


DISH_CALORIE_RANGES = [
    ("Dunkin coffee roll", 300, 600, "A single Dunkin coffee roll: ~400-490 kcal"),
    ("large iced latte with whole milk", 100, 400, "16-24oz latte: ~200-300 kcal"),
    ("Big Mac", 400, 700, "McDonald's Big Mac: ~550 kcal"),
    ("Chipotle chicken burrito", 700, 1500, "Full chicken burrito: ~1000-1200 kcal"),
    ("slice of pepperoni pizza", 200, 450, "One slice: ~300-350 kcal"),
    ("bowl of cereal with whole milk", 200, 450, "1 cup cereal + 1 cup milk: ~300 kcal"),
]


class TestEndToEndDishCaloriesLive:
    """Full pipeline: dish description → recipe suggestion → nutrient profiles → total calories."""

    async def _estimate_dish_calories(self, description: str) -> tuple[float, list[dict]]:
        """Run the full pipeline and return (total_cal, ingredient_details)."""
        agent = _make_agent()

        suggestion = await agent._suggest_recipe(description)
        assert suggestion is not None, f"No recipe for '{description}'"

        servings = suggestion["recipe"]["servings"]
        assert servings >= 1

        total_cal = 0.0
        details = []

        for item in suggestion["ingredients"]:
            food_name = item["name"]
            unit = item["unit"]
            qty = item["quantity"]
            per_serving_qty = qty / servings

            profile = await agent._fetch_nutrient_profile(food_name, unit)

            cal_per_unit = profile.get("calories") or 0
            item_cal = cal_per_unit * per_serving_qty
            total_cal += item_cal
            details.append({
                "name": food_name, "qty": per_serving_qty, "unit": unit,
                "cal_per_unit": cal_per_unit, "cal_total": item_cal,
            })

        return total_cal, details

    @pytest.mark.asyncio
    @pytest.mark.live_llm
    @pytest.mark.parametrize(
        "description,min_cal,max_cal,explanation",
        DISH_CALORIE_RANGES,
        ids=[r[0] for r in DISH_CALORIE_RANGES],
    )
    async def test_dish_calories_in_range(
        self, description: str, min_cal: float, max_cal: float, explanation: str
    ):
        """Total estimated calories should be within known range for the dish."""
        _require_live_llm()
        total, details = await self._estimate_dish_calories(description)
        detail_str = "\n".join(
            f"  {d['name']}: {d.get('qty', '?')} {d.get('unit', '?')} "
            f"→ {d.get('cal_total', d.get('cal', '?')):.0f} kcal"
            for d in details
        )
        assert min_cal <= total <= max_cal, (
            f"'{description}' estimated at {total:.0f} kcal, "
            f"expected {min_cal}-{max_cal} ({explanation})\n"
            f"Ingredient breakdown:\n{detail_str}"
        )
