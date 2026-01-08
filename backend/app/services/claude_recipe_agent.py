from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
import asyncio

from google import genai
from google.genai.types import GenerateContentConfig
from loguru import logger

from app.core.config import settings
from app.prompts import CLAUDE_RECIPE_SUGGESTION_PROMPT


@dataclass
class RecipeSuggestionResult:
    recipe: dict[str, Any]
    ingredients: list[dict[str, Any]]


class ClaudeRecipeAgent:
    def __init__(self) -> None:
        self.client = genai.Client()
        self.model_name = settings.vertex_model_name or "gemini-2.5-flash"

    async def suggest(self, description: str) -> RecipeSuggestionResult | None:
        prompt = CLAUDE_RECIPE_SUGGESTION_PROMPT.format(description=description)

        def _invoke() -> str:
            config = GenerateContentConfig()
            result = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return result.text or ""

        text = await asyncio.to_thread(_invoke)
        logger.info("[claude] recipe suggestion chars=%s", len(text))
        data = self._extract_json(text)
        if not data or not isinstance(data, dict):
            return None
        recipe = data.get("recipe") or {}
        ingredients = data.get("ingredients") or []
        if not isinstance(recipe, dict) or not isinstance(ingredients, list):
            return None
        return RecipeSuggestionResult(recipe=recipe, ingredients=ingredients)

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
        return None
