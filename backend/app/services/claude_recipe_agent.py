from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.clients.openai_client import OpenAIResponsesClient
from app.prompts import RECIPE_SUGGESTION_PROMPT
from app.schemas.llm_outputs import RecipeSuggestionOutput


@dataclass
class RecipeSuggestionResult:
    recipe: dict[str, Any]
    ingredients: list[dict[str, Any]]


class RecipeSuggestionAgent:
    def __init__(self) -> None:
        self.client = OpenAIResponsesClient()

    async def suggest(self, description: str) -> RecipeSuggestionResult | None:
        prompt = RECIPE_SUGGESTION_PROMPT.format(description=description)
        try:
            result = await self.client.generate_json(
                prompt,
                response_model=RecipeSuggestionOutput,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("[llm-fallback] claude_recipe_agent.suggest failed: {}", exc)
            return None
        text = result.text
        logger.info("[nutrition] recipe suggestion chars=%s", len(text))
        return RecipeSuggestionResult(
            recipe=result.data.recipe.model_dump(),
            ingredients=[item.model_dump() for item in result.data.ingredients],
        )
