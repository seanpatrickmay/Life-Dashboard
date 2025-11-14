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

from google import genai
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool

try:  # google-genai < 0.5.0 ships HttpOptions elsewhere / omits it entirely
    from google.genai.types import HttpOptions
except ImportError:  # pragma: no cover - runtime shim for docker image
    HttpOptions = None  # type: ignore[assignment]
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.prompts import CLAUDE_FOOD_EXTRACTION_PROMPT, CLAUDE_NUTRIENT_PROFILE_PROMPT
from app.db.models.nutrition import (
    NUTRIENT_COLUMN_BY_SLUG,
    NUTRIENT_DEFINITIONS,
    NutritionFoodStatus,
    NutritionIntakeSource,
)
from app.db.repositories.nutrition_foods_repository import NutritionFoodsRepository
from app.db.repositories.nutrition_intake_repository import NutritionIntakeRepository
from app.utils.timezone import eastern_today


@dataclass
class ClaudeResponse:
    reply: str
    logged_entries: list[dict[str, Any]]


class ClaudeNutritionAgent:
    """Nutrition mentor that uses Gemini via Vertex AI for parsing + grounding."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.food_repo = NutritionFoodsRepository(session)
        self.intake_repo = NutritionIntakeRepository(session)
        http_options = HttpOptions(api_version="v1") if HttpOptions else None
        client_kwargs = {"http_options": http_options} if http_options else {}
        self.client = genai.Client(**client_kwargs)
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
            quantity = self._safe_float(item.get("quantity")) or 1.0
            unit = item.get("unit") or "serving"

            food = await self.food_repo.get_food_by_name(name)
            created = False
            if food is None:
                nutrients = await self._fetch_nutrient_profile(name, unit)
                try:
                    food = await self.food_repo.create_food(
                        name=name,
                        default_unit=unit,
                        source="claude",
                        status=NutritionFoodStatus.UNCONFIRMED,
                        nutrient_values=nutrients,
                    )
                    created = True
                    logger.info(f"[claude] created new food={name} id={food.id}")
                except Exception as exc:  # pragma: no cover - safety net
                    logger.exception("Failed to create food %s: %s", name, exc)
                    continue

            await self.intake_repo.log_intake(
                user_id=user_id,
                food_id=food.id,
                quantity=quantity,
                unit=unit,
                day=eastern_today(),
                source=NutritionIntakeSource.CLAUDE,
                claude_request_id=request_id,
            )

            entries.append(
                {
                    "food_id": food.id,
                    "food_name": food.name,
                    "quantity": quantity,
                    "unit": unit,
                    "status": food.status.value,
                    "created": created,
                }
            )

        await self.session.flush()
        await self.session.commit()
        logger.info(
            f"[claude] logged {len(entries)} entries for request id={request_id}"
        )

        reply = parsed.get("summary") or self._build_summary(entries)
        if any(
            entry["status"] == NutritionFoodStatus.UNCONFIRMED.value
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
        parts = [
            f"{entry['quantity']} {entry['unit']} {entry['food_name']} ({entry['status']})"
            for entry in entries
        ]
        return "Logged: " + ", ".join(parts)

    def _safe_float(self, value: Any) -> float | None:
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None
