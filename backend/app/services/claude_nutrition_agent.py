"""Nutrition assistant backed by the OpenAI Responses API."""

from __future__ import annotations

import asyncio
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
    FuzzyMatchOutput,
    NutritionFoodExtractionOutput,
    NutrientProfileOutput,
    RecipeSuggestionOutput,
)
from app.services.nutrition_units import NutritionUnitNormalizer
from app.utils.timezone import eastern_today


_FUZZY_MATCH_PROMPT = (
    "The user is trying to log a food called: \"{query}\"\n\n"
    "Here are existing items in their database:\n{candidates}\n\n"
    "Does one of these match what the user means? Consider that brand names, "
    "parenthetical qualifiers, and word order differences are superficial — "
    "\"coffee roll from dunkin\" matches \"Coffee Roll (Dunkin)\".\n\n"
    "Return the id of the best match, or null if none are a reasonable match."
)


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

            ingredient = await self._find_matching_ingredient(user_id, name)
            recipe = await self._find_matching_recipe(user_id, name) if ingredient is None else None

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
            try:
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
            except Exception as exc:  # noqa: BLE001
                logger.exception("[nutrition] failed to create/log recipe for '%s': %s", name, exc)
                continue

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
            logger.error("[llm-fallback] nutrition_agent._extract_food_mentions failed: {}", exc)
            return {"foods": [], "summary": None}
        return result.data.model_dump()

    async def _find_matching_ingredient(
        self, user_id: int, name: str
    ) -> NutritionIngredient | None:
        exact = await self.ingredients_repo.get_ingredient_by_name(user_id, name)
        if exact is not None:
            return exact
        candidates = await self.ingredients_repo.search_ingredients_fuzzy(user_id, name, limit=5)
        if not candidates:
            return None
        return await self._llm_rerank_match(
            name, [(c.id, c.name) for c in candidates], {c.id: c for c in candidates}
        )

    async def _find_matching_recipe(
        self, user_id: int, name: str
    ) -> NutritionRecipe | None:
        exact = await self.recipes_repo.get_recipe_by_name(user_id, name)
        if exact is not None:
            return exact
        candidates = await self.recipes_repo.search_recipes_fuzzy(user_id, name, limit=5)
        if not candidates:
            return None
        return await self._llm_rerank_match(
            name, [(c.id, c.name) for c in candidates], {c.id: c for c in candidates}
        )

    async def _llm_rerank_match(
        self,
        query: str,
        candidate_pairs: list[tuple[int, str]],
        lookup: dict[int, Any],
    ) -> Any | None:
        candidate_text = "\n".join(f"- [id={cid}] {cname}" for cid, cname in candidate_pairs)
        prompt = _FUZZY_MATCH_PROMPT.format(query=query, candidates=candidate_text)
        try:
            result = await self.client.generate_json(prompt, response_model=FuzzyMatchOutput)
            match_id = result.data.match_id
        except Exception as exc:  # noqa: BLE001
            logger.error("[llm-fallback] nutrition_agent._llm_rerank_match failed for '{}': {}", query, exc)
            return None
        if match_id is None:
            logger.info("[nutrition] fuzzy rerank: no match for '{}'", query)
            return None
        matched = lookup.get(match_id)
        if matched is not None:
            logger.info("[nutrition] fuzzy rerank: '{}' → id={} ({})", query, match_id, result.data.reason)
        return matched

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
            data = result.data.model_dump()
        except Exception as exc:  # noqa: BLE001
            logger.error("[llm-fallback] nutrition_agent._fetch_nutrient_profile failed for {}: {}", food_name, exc)
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
            logger.error("[llm-fallback] nutrition_agent._suggest_recipe failed for {}: {}", description, exc)
            return None
        return {
            "recipe": result.data.recipe.model_dump(),
            "ingredients": [item.model_dump() for item in result.data.ingredients],
        }

    # Per-serving clamp limits by unit (keeps LLM hallucinated quantities sane)
    _CLAMP_LIMITS: dict[str, float] = {
        # Volume – small
        "tsp": 12.0, "teaspoon": 12.0,
        "tbsp": 8.0, "tablespoon": 8.0,
        # Volume – medium
        "fl oz": 32.0, "fl_oz": 32.0,
        "cup": 6.0, "cups": 6.0,
        "ml": 1000.0, "milliliter": 1000.0,
        # Volume – large
        "l": 2.0, "liter": 2.0,
        # Weight – small
        "g": 1000.0, "gram": 1000.0, "grams": 1000.0,
        "oz": 32.0, "ounce": 32.0, "ounces": 32.0,
        # Weight – large
        "kg": 2.0, "lb": 4.0, "lbs": 4.0,
        # Discrete
        "piece": 10.0, "pieces": 10.0, "whole": 6.0,
        "shot": 6.0, "shots": 6.0,
        "slice": 10.0, "slices": 10.0,
    }
    _DEFAULT_CLAMP = 20.0

    @classmethod
    def _clamp_per_serving_qty(cls, qty: float, servings: float, unit: str) -> float:
        """Clamp ingredient quantity so per-serving amount stays realistic."""
        effective_servings = servings if servings > 0 else 1.0
        per_serving = qty / effective_servings
        unit_lower = unit.lower().strip()
        max_per_serving = cls._CLAMP_LIMITS.get(unit_lower, cls._DEFAULT_CLAMP)
        if per_serving > max_per_serving:
            logger.warning(
                "[nutrition] clamping ingredient qty: {:.1f} {} / {:.0f} servings = {:.1f} per serving (max {})",
                qty, unit, servings, per_serving, max_per_serving,
            )
            return max_per_serving * effective_servings
        return qty

    async def _ensure_recipe_from_suggestion(
        self, *, owner_user_id: int, suggestion: dict[str, Any]
    ) -> NutritionRecipe:
        recipe_data = suggestion.get("recipe") or {}
        ingredient_rows = suggestion.get("ingredients") or []

        name = recipe_data.get("name") or "Untitled recipe"
        default_unit = recipe_data.get("default_unit") or "serving"
        servings = self._safe_float(recipe_data.get("servings")) or 1.0

        # Phase 1: resolve existing ingredients and identify missing ones
        parsed_rows: list[dict[str, Any]] = []
        missing_indices: list[int] = []
        for raw in ingredient_rows:
            ing_name = (raw.get("name") or "").strip()
            if not ing_name:
                continue
            raw_qty = self._safe_float(raw.get("quantity")) or 1.0
            unit = (raw.get("unit") or "100g").strip()
            qty = self._clamp_per_serving_qty(raw_qty, servings, unit)
            ingredient = await self._find_matching_ingredient(owner_user_id, ing_name)
            entry = {"name": ing_name, "unit": unit, "qty": qty, "ingredient": ingredient}
            parsed_rows.append(entry)
            if ingredient is None:
                missing_indices.append(len(parsed_rows) - 1)

        # Phase 2: fetch nutrient profiles for missing ingredients in parallel
        if missing_indices:
            fetch_tasks = [
                self._fetch_nutrient_profile(parsed_rows[i]["name"], parsed_rows[i]["unit"])
                for i in missing_indices
            ]
            nutrient_results = await asyncio.gather(*fetch_tasks)

            # Phase 3: create ingredients sequentially (DB writes aren't concurrency-safe)
            for idx, nutrients in zip(missing_indices, nutrient_results):
                row = parsed_rows[idx]
                ingredient = await self.ingredients_repo.create_ingredient(
                    name=row["name"],
                    default_unit=row["unit"],
                    source="claude",
                    nutrient_values=nutrients,
                    owner_user_id=owner_user_id,
                    status=NutritionIngredientStatus.UNCONFIRMED,
                )
                row["ingredient"] = ingredient
                logger.info("[nutrition] created ingredient={} id={}", row["name"], ingredient.id)

        components = [
            {
                "ingredient_id": row["ingredient"].id,
                "quantity": row["qty"],
                "unit": row["unit"],
                "created": row["ingredient"] is not None,
            }
            for row in parsed_rows
            if row["ingredient"] is not None
        ]

        recipe = await self._find_matching_recipe(owner_user_id, name)
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
            logger.info("[nutrition] created recipe name={} id={}", name, recipe.id)
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
                        recipe_id=recipe.id,
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
