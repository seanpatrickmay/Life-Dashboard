"""Claude-style nutrition agent backed by Google GenAI + Vertex AI."""

from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from google.genai.types import GenerateContentConfig, GoogleSearch, Tool

try:  # google-genai < 0.5.0 ships HttpOptions elsewhere / omits it entirely
    from google.genai.types import HttpOptions
except ImportError:  # pragma: no cover - runtime shim for docker image
    HttpOptions = None  # type: ignore[assignment]
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.clients.genai_client import build_genai_client
from app.prompts import (
    CLAUDE_FOOD_EXTRACTION_PROMPT,
    CLAUDE_NUTRIENT_PROFILE_PROMPT,
    CLAUDE_RECIPE_SUGGESTION_PROMPT,
)
from app.db.models.nutrition import (
    NUTRIENT_COLUMN_BY_SLUG,
    NUTRIENT_DEFINITIONS,
    NutritionIngredient,
    NutritionIngredientStatus,
    NutritionRecipe,
    NutritionIntakeSource,
)
from app.db.repositories.nutrition_ingredients_repository import (
    NutritionIngredientsRepository,
    NutritionRecipesRepository,
)
from app.db.repositories.nutrition_intake_repository import NutritionIntakeRepository
from app.services.nutrition_units import NutritionUnitNormalizer
from app.utils.timezone import eastern_today


@dataclass
class ClaudeResponse:
    reply: str
    logged_entries: list[dict[str, Any]]


class ClaudeNutritionAgent:
    """Nutrition mentor that uses Gemini via Vertex AI for parsing + grounding."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingredients_repo = NutritionIngredientsRepository(session)
        self.recipes_repo = NutritionRecipesRepository(session)
        self.intake_repo = NutritionIntakeRepository(session)
        self.unit_normalizer = NutritionUnitNormalizer()
        http_options = HttpOptions(api_version="v1") if HttpOptions else None
        self.client = build_genai_client(http_options=http_options)
        self.model_name = settings.vertex_model_name or "gemini-2.5-flash"
        self.search_tool = Tool(google_search=GoogleSearch())

    async def respond(
        self, user_id: int, message: str, request_id: str | None = None
    ) -> ClaudeResponse:
        request_id = request_id or str(uuid4())
        logger.info(
            f"[claude] respond start id={request_id} user={user_id} text={message}"
        )
        parsed = await self._extract_food_mentions(message)
        logger.info(
            f"[claude] parsed foods={parsed.get('foods')} summary={parsed.get('summary')}"
        )
        if not parsed["foods"]:
            logger.info(f"[claude] no foods detected for request id={request_id}")
            return ClaudeResponse(
                reply="I couldn't recognize any foods. Try something like ‘I ate two eggs and a banana.’",
                logged_entries=[],
            )

        entries: list[dict[str, Any]] = []
        for item in parsed["foods"]:
            name = item.get("name", "").strip()
            if not name:
                continue
            raw_quantity = self._safe_float(item.get("quantity"))
            quantity = raw_quantity if raw_quantity and raw_quantity > 0 else 1.0
            unit = (item.get("unit") or "serving").strip()

            ingredient = await self.ingredients_repo.get_ingredient_by_name(user_id, name)
            recipe = await self.ingredients_repo.get_recipe_by_name(user_id, name)

            if ingredient:
                normalized = self.unit_normalizer.normalize(
                    quantity=quantity,
                    unit=unit,
                    target_unit=ingredient.default_unit,
                )
                await self.intake_repo.log_intake(
                    user_id=user_id,
                    food_id=ingredient.id,
                    quantity=normalized.quantity,
                    unit=normalized.unit,
                    day=eastern_today(),
                    source=NutritionIntakeSource.CLAUDE,
                    claude_request_id=request_id,
                )
                entries.append(
                    {
                        "ingredient_id": ingredient.id,
                        "food_name": ingredient.name,
                        "ingredient_name": ingredient.name,
                        "quantity": normalized.quantity,
                        "unit": normalized.unit,
                        "input_quantity": normalized.input_quantity,
                        "input_unit": normalized.input_unit,
                        "display": normalized.display,
                        "converted": normalized.converted,
                        "status": ingredient.status.value,
                        "created": False,
                    }
                )
                continue

            if recipe:
                await self._log_recipe(recipe_id=recipe.id, servings=quantity, user_id=user_id, request_id=request_id)
                entries.append(
                    {
                        "recipe_id": recipe.id,
                        "food_name": recipe.name,
                        "quantity": quantity,
                        "unit": unit,
                        "status": recipe.status.value,
                        "created": False,
                    }
                )
                continue

            # Unknown dish: ask recipe agent for structure, create ingredients + recipe, then log
            suggestion = await self._suggest_recipe(name)
            if suggestion is None:
                logger.info("[claude] no recipe suggestion for %s", name)
                continue
            created_recipe = await self._ensure_recipe_from_suggestion(
                owner_user_id=user_id,
                suggestion=suggestion,
            )
            await self._log_recipe(
                recipe_id=created_recipe.id,
                servings=quantity,
                user_id=user_id,
                request_id=request_id,
            )
            entries.append(
                {
                    "recipe_id": created_recipe.id,
                    "food_name": created_recipe.name,
                    "quantity": quantity,
                    "unit": unit,
                    "status": created_recipe.status.value,
                    "created": True,
                }
            )

        await self.session.flush()
        await self.session.commit()
        logger.info(
            f"[claude] logged {len(entries)} entries for request id={request_id}"
        )

        reply = parsed.get("summary") or self._build_summary(entries)
        if any(
            entry["status"] == NutritionIngredientStatus.UNCONFIRMED.value
            for entry in entries
        ):
            reply += "\nNote: items marked unconfirmed still need a quick review."

        logger.info(f"[claude] respond complete id={request_id} reply={reply}")
        return ClaudeResponse(reply=reply, logged_entries=entries)

    async def _extract_food_mentions(self, user_text: str) -> dict[str, Any]:
        prompt = CLAUDE_FOOD_EXTRACTION_PROMPT.format(user_text=user_text)
        response = await self._call_model(prompt, use_search=False)
        return self._extract_json(response) or {"foods": [], "summary": None}

    async def _fetch_nutrient_profile(
        self, food_name: str, unit: str
    ) -> dict[str, float | None]:
        logger.info(f"[claude] fetching nutrient profile food={food_name} unit={unit}")
        nutrient_list = ", ".join(
            definition.slug for definition in NUTRIENT_DEFINITIONS
        )
        prompt = CLAUDE_NUTRIENT_PROFILE_PROMPT.format(
            food_name=food_name,
            unit=unit,
            nutrient_list=nutrient_list,
        )
        response = await self._call_model(prompt, use_search=True)
        data = self._extract_json(response) or {}
        nutrients: dict[str, float | None] = {}
        for slug in NUTRIENT_COLUMN_BY_SLUG:
            value = self._safe_float(data.get(slug)) if isinstance(data, dict) else None
            nutrients[slug] = value
        logger.info(f"[claude] nutrient profile resolved for {food_name}")
        return nutrients

    async def _suggest_recipe(self, description: str) -> dict[str, Any] | None:
        prompt = CLAUDE_RECIPE_SUGGESTION_PROMPT.format(description=description)
        text = await self._call_model(prompt, use_search=False)
        data = self._extract_json(text)
        if not data or not isinstance(data, dict):
            return None
        recipe = data.get("recipe")
        ingredients = data.get("ingredients")
        if not isinstance(recipe, dict) or not isinstance(ingredients, list):
            return None
        return {"recipe": recipe, "ingredients": ingredients}

    async def _ensure_recipe_from_suggestion(
        self, *, owner_user_id: int, suggestion: dict[str, Any]
    ) -> NutritionRecipe:
        recipe_data = suggestion.get("recipe") or {}
        ingredient_rows = suggestion.get("ingredients") or []

        name = recipe_data.get("name") or "Untitled recipe"
        default_unit = recipe_data.get("default_unit") or "serving"
        servings = self._safe_float(recipe_data.get("servings")) or 1.0

        components: list[dict[str, Any]] = []

        for raw in ingredient_rows:
            ing_name = (raw.get("name") or "").strip()
            if not ing_name:
                continue
            qty = self._safe_float(raw.get("quantity")) or 1.0
            unit = (raw.get("unit") or "100g").strip()
            ingredient = await self.ingredients_repo.get_ingredient_by_name(owner_user_id, ing_name)
            created = False
            if ingredient is None:
                nutrients = await self._fetch_nutrient_profile(ing_name, unit)
                ingredient = await self.ingredients_repo.create_ingredient(
                    name=ing_name,
                    default_unit=unit,
                    source="claude",
                    nutrient_values=nutrients,
                    owner_user_id=owner_user_id,
                    status=NutritionIngredientStatus.UNCONFIRMED,
                )
                created = True
                logger.info(f"[claude] created ingredient={ing_name} id={ingredient.id}")
            components.append(
                {
                    "ingredient_id": ingredient.id,
                    "quantity": qty,
                    "unit": unit,
                    "created": created,
                }
            )

        recipe = await self.recipes_repo.get_recipe_by_name(owner_user_id, name)
        if recipe is None:
            recipe = await self.recipes_repo.create_recipe(
                name=name,
                default_unit=default_unit,
                servings=servings,
                status=NutritionIngredientStatus.UNCONFIRMED,
                owner_user_id=owner_user_id,
                components=components,
                source="claude",
            )
            logger.info(f"[claude] created recipe name={name} id={recipe.id}")
            recipe = await self.recipes_repo.get_recipe(recipe.id, owner_user_id, load_components=True)
        return recipe

    async def _log_recipe(
        self,
        *,
        recipe_id: int,
        servings: float,
        user_id: int,
        request_id: str,
    ) -> None:
        recipe = await self.recipes_repo.get_recipe(recipe_id, user_id, load_components=True)
        if recipe is None:
            raise ValueError("Recipe not found")

        async def _expand(target_recipe, multiplier: float) -> None:
            for comp in target_recipe.components:
                per_serving = comp.quantity / target_recipe.servings if target_recipe.servings else comp.quantity
                effective_qty = multiplier * per_serving
                if comp.ingredient:
                    normalized = self.unit_normalizer.normalize(
                        quantity=effective_qty,
                        unit=comp.unit,
                        target_unit=comp.ingredient.default_unit,
                    )
                    await self.intake_repo.log_intake(
                        user_id=user_id,
                        food_id=comp.ingredient.id,
                        quantity=normalized.quantity,
                        unit=normalized.unit,
                        day=eastern_today(),
                        source=NutritionIntakeSource.CLAUDE,
                        claude_request_id=request_id,
                    )
                elif comp.child_recipe:
                    await _expand(comp.child_recipe, effective_qty)

        await _expand(recipe, servings)

    async def _call_model(self, prompt: str, use_search: bool) -> str:
        def _invoke() -> str:
            config = GenerateContentConfig()
            if use_search:
                config.tools = [self.search_tool]
            logger.info(f"[claude] model call start search={use_search}")
            result = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            text = result.text or ""
            logger.info(
                f"[claude] model call complete chars={len(text)} search={use_search}"
            )
            return text

        return await asyncio.to_thread(_invoke)

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

    def _build_summary(self, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return "No items were logged."
        parts = []
        for entry in entries:
            display = entry.get("display")
            base = (
                f"{entry['quantity']} {entry['unit']}"
                if display in (None, "")
                else display
            )
            summary = f"{base} {entry['food_name']} ({entry['status']})"
            if entry.get("converted"):
                summary += f" → saved as {entry['quantity']:.3g} {entry['unit']}"
            parts.append(summary)
        return "Logged: " + ", ".join(parts)

    def _safe_float(self, value: Any) -> float | None:
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None
