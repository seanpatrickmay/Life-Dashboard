"""Nutrition assistant backed by the OpenAI Responses API."""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openai_client import OpenAIResponsesClient
from app.prompts import (
    NUTRITION_FOOD_EXTRACTION_PROMPT,
    NUTRIENT_PROFILE_PROMPT,
    RECIPE_SUGGESTION_PROMPT,
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
from app.db.repositories.nutrition_suggestions_repository import NutritionSuggestionsRepository
from app.schemas.llm_outputs import (
    NutritionFoodExtractionOutput,
    NutrientProfileOutput,
    RecipeSuggestionOutput,
)
from app.services.nutrition_units import NutritionUnitNormalizer
from app.utils.timezone import eastern_today


@dataclass
class _ConversationTurn:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


class _ConversationMemory:
    """In-memory LRU conversation store with TTL expiry (no DB migration needed)."""

    MAX_SESSIONS = 64
    MAX_TURNS_PER_SESSION = 20
    TTL_SECONDS = 3600  # 1 hour

    def __init__(self) -> None:
        self._sessions: OrderedDict[str, list[_ConversationTurn]] = OrderedDict()

    def get_history(self, session_id: str) -> list[_ConversationTurn]:
        self._evict_expired()
        turns = self._sessions.get(session_id, [])
        self._sessions.move_to_end(session_id, last=True) if session_id in self._sessions else None
        return turns

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        self._evict_expired()
        if session_id not in self._sessions:
            if len(self._sessions) >= self.MAX_SESSIONS:
                self._sessions.popitem(last=False)
            self._sessions[session_id] = []
        self._sessions[session_id].append(_ConversationTurn(role=role, content=content))
        if len(self._sessions[session_id]) > self.MAX_TURNS_PER_SESSION:
            self._sessions[session_id] = self._sessions[session_id][-self.MAX_TURNS_PER_SESSION:]
        self._sessions.move_to_end(session_id, last=True)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [
            sid for sid, turns in self._sessions.items()
            if turns and (now - turns[-1].timestamp) > self.TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]


# Module-level singleton so memory persists across requests within the process
_conversation_memory = _ConversationMemory()


@dataclass
class NutritionAssistantResponse:
    reply: str
    logged_entries: list[dict[str, Any]]


class NutritionAssistantAgent:
    """Nutrition mentor that uses OpenAI for parsing and nutrient grounding."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingredients_repo = NutritionIngredientsRepository(session)
        self.recipes_repo = NutritionRecipesRepository(session)
        self.intake_repo = NutritionIntakeRepository(session)
        self.unit_normalizer = NutritionUnitNormalizer()
        self.client = OpenAIResponsesClient()
        self.memory = _conversation_memory

    async def respond(
        self, user_id: int, message: str, request_id: str | None = None
    ) -> NutritionAssistantResponse:
        request_id = request_id or str(uuid4())
        logger.info(
            f"[nutrition] respond start id={request_id} user={user_id} text={message}"
        )
        self.memory.add_turn(request_id, "user", message)
        history = self.memory.get_history(request_id)
        context_text = self._build_conversation_context(message, history)
        parsed = await self._extract_food_mentions(context_text)
        logger.info(
            f"[nutrition] parsed foods={parsed.get('foods')} summary={parsed.get('summary')}"
        )
        if not parsed["foods"]:
            logger.info(f"[nutrition] no foods detected for request id={request_id}")
            return NutritionAssistantResponse(
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
                logger.info("[nutrition] no recipe suggestion for %s", name)
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
        suggestions_repo = NutritionSuggestionsRepository(self.session)
        await suggestions_repo.mark_stale(user_id)
        await self.session.commit()
        logger.info(
            f"[nutrition] logged {len(entries)} entries for request id={request_id}"
        )

        reply = parsed.get("summary") or self._build_summary(entries)
        if any(
            entry["status"] == NutritionIngredientStatus.UNCONFIRMED.value
            for entry in entries
        ):
            reply += "\nNote: items marked unconfirmed still need a quick review."

        self.memory.add_turn(request_id, "assistant", reply)
        logger.info(f"[nutrition] respond complete id={request_id} reply={reply}")
        return NutritionAssistantResponse(reply=reply, logged_entries=entries)

    def _build_conversation_context(
        self, current_message: str, history: list[_ConversationTurn]
    ) -> str:
        """Build context-aware prompt text from conversation history."""
        if len(history) <= 1:
            return current_message
        prior_turns = [
            t for t in history
            if not (t.role == "user" and t.content == current_message and t is history[-1])
        ]
        if not prior_turns:
            return current_message
        context_lines = ["Previous conversation:"]
        for turn in prior_turns[:-1]:
            prefix = "User" if turn.role == "user" else "Assistant"
            context_lines.append(f"  {prefix}: {turn.content}")
        context_lines.append(f"\nCurrent message: {current_message}")
        return "\n".join(context_lines)

    async def _extract_food_mentions(self, user_text: str) -> dict[str, Any]:
        prompt = NUTRITION_FOOD_EXTRACTION_PROMPT.format(user_text=user_text)
        try:
            result = await self.client.generate_json(
                prompt,
                response_model=NutritionFoodExtractionOutput,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[nutrition] food extraction failed: {}", exc)
            return {"foods": [], "summary": None}
        return result.data.model_dump()

    async def _fetch_nutrient_profile(
        self, food_name: str, unit: str
    ) -> dict[str, float | None]:
        logger.info(f"[nutrition] fetching nutrient profile food={food_name} unit={unit}")
        nutrient_list = ", ".join(
            definition.slug for definition in NUTRIENT_DEFINITIONS
        )
        prompt = NUTRIENT_PROFILE_PROMPT.format(
            food_name=food_name,
            unit=unit,
            nutrient_list=nutrient_list,
        )
        try:
            result = await self.client.generate_json_with_web_search(
                prompt,
                response_model=NutrientProfileOutput,
            )
            data = result.data.root
        except Exception as exc:  # noqa: BLE001
            logger.warning("[nutrition] nutrient lookup failed for {}: {}", food_name, exc)
            data = {}
        nutrients: dict[str, float | None] = {}
        for slug in NUTRIENT_COLUMN_BY_SLUG:
            value = self._safe_float(data.get(slug))
            nutrients[slug] = value
        logger.info(f"[nutrition] nutrient profile resolved for {food_name}")
        return nutrients

    async def _suggest_recipe(self, description: str) -> dict[str, Any] | None:
        prompt = RECIPE_SUGGESTION_PROMPT.format(description=description)
        try:
            result = await self.client.generate_json(
                prompt,
                response_model=RecipeSuggestionOutput,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[nutrition] recipe suggestion failed for {}: {}", description, exc)
            return None
        return {
            "recipe": result.data.recipe.model_dump(),
            "ingredients": [item.model_dump() for item in result.data.ingredients],
        }

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
                logger.info(f"[nutrition] created ingredient={ing_name} id={ingredient.id}")
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
            logger.info(f"[nutrition] created recipe name={name} id={recipe.id}")
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
