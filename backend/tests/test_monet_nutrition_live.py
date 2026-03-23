"""Live end-to-end test reproducing the Monet chatbot nutrition pipeline.

Tests the exact code path: MonetAssistantAgent.respond() → router → NutritionLogTool → NutritionAssistantAgent.

Run:  python3 -m pytest tests/test_monet_nutrition_live.py -v -s
"""
from __future__ import annotations

import traceback

from app.core.config import get_settings
get_settings.cache_clear()

import pytest
from loguru import logger

pytestmark = pytest.mark.live_llm


def _require_live_llm() -> None:
    """Skip this test unless RUN_LIVE_LLM_TESTS=1 is set in the environment."""
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to run live LLM evaluations.")


@pytest.fixture(autouse=True)
def _gate_live_llm():
    _require_live_llm()


# ── Stage 1: OpenAI client basics ──────────────────────────────────────────

class TestStage1OpenAIClient:
    """Verify that the OpenAI client can make calls at all."""

    @pytest.mark.asyncio
    async def test_generate_text(self):
        from app.clients.openai_client import OpenAIResponsesClient
        client = OpenAIResponsesClient()
        result = await client.generate_text("Say 'hello' and nothing else.", temperature=0.0)
        assert result.text, "generate_text returned empty"
        logger.info(f"[stage1] generate_text OK: {result.text!r}")

    @pytest.mark.asyncio
    async def test_generate_json(self):
        from app.clients.openai_client import OpenAIResponsesClient
        from app.schemas.llm_outputs import NutritionFoodExtractionOutput
        client = OpenAIResponsesClient()
        result = await client.generate_json(
            "Extract foods from: 'I ate a banana'. Return {foods: [{name, quantity, unit}], summary}.",
            response_model=NutritionFoodExtractionOutput,
        )
        assert result.data, "generate_json returned no data"
        data = result.data.model_dump()
        logger.info(f"[stage1] generate_json OK: {data}")
        assert len(data["foods"]) >= 1

    @pytest.mark.asyncio
    async def test_generate_json_with_web_search(self):
        from app.clients.openai_client import OpenAIResponsesClient
        from app.schemas.llm_outputs import NutrientProfileOutput
        from app.db.models.nutrition import NUTRIENT_DEFINITIONS
        client = OpenAIResponsesClient()
        nutrient_list = ", ".join(d.slug for d in NUTRIENT_DEFINITIONS)
        prompt = f"Estimate nutrients per 1 serving of banana. Fields: {nutrient_list}."
        result = await client.generate_json_with_web_search(
            prompt,
            response_model=NutrientProfileOutput,
        )
        assert result.data, "generate_json_with_web_search returned no data"
        data = result.data.model_dump()
        logger.info(f"[stage1] web_search OK: calories={data.get('calories')}")
        assert data.get("calories") is not None, "Expected calories for banana"


# ── Stage 2: Food extraction ──────────────────────────────────────────────

class TestStage2FoodExtraction:
    """Verify food extraction from the exact user message."""

    @pytest.mark.asyncio
    async def test_extract_dunkin_foods(self):
        from app.clients.openai_client import OpenAIResponsesClient
        from app.prompts import NUTRITION_FOOD_EXTRACTION_PROMPT
        from app.schemas.llm_outputs import NutritionFoodExtractionOutput

        client = OpenAIResponsesClient()
        user_text = "I had a large iced latte from dunkin and a coffee roll from dunkin too"
        prompt = NUTRITION_FOOD_EXTRACTION_PROMPT.format(user_text=user_text)
        result = await client.generate_json(prompt, response_model=NutritionFoodExtractionOutput)
        data = result.data.model_dump()
        foods = data["foods"]
        logger.info(f"[stage2] extracted foods: {foods}")
        assert len(foods) >= 2, f"Expected >=2 foods, got {len(foods)}: {foods}"
        names = [f["name"].lower() for f in foods]
        assert any("latte" in n for n in names), f"No latte found in {names}"
        assert any("coffee roll" in n or "roll" in n for n in names), f"No coffee roll in {names}"


# ── Stage 3: Recipe suggestion ────────────────────────────────────────────

class TestStage3RecipeSuggestion:
    """Verify recipe suggestion works for Dunkin items."""

    @pytest.mark.asyncio
    async def test_suggest_iced_latte(self):
        from app.clients.openai_client import OpenAIResponsesClient
        from app.prompts import RECIPE_SUGGESTION_PROMPT
        from app.schemas.llm_outputs import RecipeSuggestionOutput

        client = OpenAIResponsesClient()
        prompt = RECIPE_SUGGESTION_PROMPT.format(description="large iced latte from Dunkin")
        result = await client.generate_json(prompt, response_model=RecipeSuggestionOutput)
        data = result.data
        logger.info(f"[stage3] recipe: {data.recipe.name}, ingredients: {[i.name for i in data.ingredients]}")
        assert data.recipe.name, "Empty recipe name"
        assert len(data.ingredients) >= 1, "No ingredients"

    @pytest.mark.asyncio
    async def test_suggest_coffee_roll(self):
        from app.clients.openai_client import OpenAIResponsesClient
        from app.prompts import RECIPE_SUGGESTION_PROMPT
        from app.schemas.llm_outputs import RecipeSuggestionOutput

        client = OpenAIResponsesClient()
        prompt = RECIPE_SUGGESTION_PROMPT.format(description="coffee roll from Dunkin")
        result = await client.generate_json(prompt, response_model=RecipeSuggestionOutput)
        data = result.data
        logger.info(f"[stage3] recipe: {data.recipe.name}, ingredients: {[i.name for i in data.ingredients]}")
        assert data.recipe.name, "Empty recipe name"
        assert len(data.ingredients) >= 1, "No ingredients"


# ── Stage 4: Nutrient profile ─────────────────────────────────────────────

class TestStage4NutrientProfile:
    """Verify nutrient profiling works (uses web search)."""

    @pytest.mark.asyncio
    async def test_milk_profile(self):
        """Test a common ingredient that would appear in a latte recipe."""
        from app.db.session import AsyncSessionLocal
        from app.services.claude_nutrition_agent import NutritionAssistantAgent

        async with AsyncSessionLocal() as session:
            agent = NutritionAssistantAgent(session)
            profile = await agent._fetch_nutrient_profile("whole milk", "cup")
            logger.info(f"[stage4] milk profile: {profile}")
            assert profile.get("calories") is not None, f"No calories for milk: {profile}"


# ── Stage 5: Full NutritionAssistantAgent.respond() ───────────────────────

class TestStage5NutritionAgent:
    """Test the full NutritionAssistantAgent directly (bypasses Monet router)."""

    @pytest.mark.asyncio
    async def test_respond_banana(self):
        """Simple single-food test."""
        from app.db.session import AsyncSessionLocal
        from app.services.claude_nutrition_agent import NutritionAssistantAgent

        async with AsyncSessionLocal() as session:
            agent = NutritionAssistantAgent(session)
            try:
                response = await agent.respond(user_id=1, message="I ate a banana")
                logger.info(f"[stage5] banana reply: {response.reply}")
                logger.info(f"[stage5] banana entries: {response.logged_entries}")
                assert response.reply, "Empty reply"
            except Exception as exc:
                logger.error(f"[stage5] banana FAILED: {exc}")
                traceback.print_exc()
                raise

    @pytest.mark.asyncio
    async def test_respond_dunkin(self):
        """The exact failing message."""
        from app.db.session import AsyncSessionLocal
        from app.services.claude_nutrition_agent import NutritionAssistantAgent

        async with AsyncSessionLocal() as session:
            agent = NutritionAssistantAgent(session)
            try:
                response = await agent.respond(
                    user_id=1,
                    message="I had a large iced latte from dunkin and a coffee roll from dunkin too",
                )
                logger.info(f"[stage5] dunkin reply: {response.reply}")
                logger.info(f"[stage5] dunkin entries: {response.logged_entries}")
                assert response.reply, "Empty reply"
            except Exception as exc:
                logger.error(f"[stage5] dunkin FAILED: {exc}")
                traceback.print_exc()
                raise


# ── Stage 6: Full MonetAssistantAgent.respond() ──────────────────────────

class TestStage6MonetAgent:
    """Test the full Monet chatbot pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_monet_dunkin(self):
        """The exact same flow the UI triggers."""
        from app.db.session import AsyncSessionLocal
        from app.services.monet_assistant import MonetAssistantAgent

        async with AsyncSessionLocal() as session:
            agent = MonetAssistantAgent(session)
            try:
                result = await agent.respond(
                    user_id=1,
                    message="I had a large iced latte from dunkin and a coffee roll from dunkin too",
                    session_id="live-test-001",
                )
                logger.info(f"[stage6] monet reply: {result.reply}")
                logger.info(f"[stage6] monet tools: {result.tools_used}")
                logger.info(f"[stage6] monet nutrition: {result.nutrition_entries}")
                # The key assertion: should NOT be the error fallback
                assert "went wrong" not in result.reply.lower(), (
                    f"Got error fallback reply: {result.reply}"
                )
            except Exception as exc:
                logger.error(f"[stage6] monet FAILED: {exc}")
                traceback.print_exc()
                raise


# ── Stage 7: Context builder ─────────────────────────────────────────────

class TestStage7ContextBuilder:
    """Test that the context builder doesn't crash."""

    @pytest.mark.asyncio
    async def test_build_context(self):
        from app.db.session import AsyncSessionLocal
        from app.services.monet_context_service import MonetContextBuilder

        async with AsyncSessionLocal() as session:
            builder = MonetContextBuilder(session)
            try:
                context = await builder.build_context(user_id=1, window_days=7)
                logger.info(f"[stage7] context keys: {list(context.keys())}")
                assert isinstance(context, dict), f"Expected dict, got {type(context)}"
            except Exception as exc:
                logger.error(f"[stage7] context builder FAILED: {exc}")
                traceback.print_exc()
                raise
