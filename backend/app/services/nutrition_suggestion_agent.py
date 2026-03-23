from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from loguru import logger

from app.clients.openai_client import OpenAIResponsesClient
from app.db.models.nutrition import NutritionIngredient, NutritionIntake
from app.db.repositories.nutrition_suggestions_repository import NutritionSuggestionsRepository
from app.prompts.nutrition_suggestion_prompt import NUTRITION_SUGGESTION_PROMPT
from app.utils.timezone import eastern_now, eastern_today


class SuggestionItemOutput(BaseModel):
    ingredient_id: int | None = None
    recipe_id: int | None = None
    name: str
    quantity: float
    unit: str
    calories_estimate: int
    reason: str


class NutritionSuggestionOutput(BaseModel):
    suggestions: list[SuggestionItemOutput]


class NutritionSuggestionAgent:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NutritionSuggestionsRepository(session)
        self.client = OpenAIResponsesClient()

    async def get_suggestions(self, user_id: int) -> list[dict]:
        row = await self.repo.get_for_user(user_id)
        if not self.repo.needs_refresh(row):
            return row.suggestions

        suggestions = await self._generate(user_id)
        await self.repo.upsert(user_id, suggestions)
        await self.session.commit()
        return suggestions

    async def _generate(self, user_id: int) -> list[dict]:
        now = eastern_now()
        today = eastern_today()
        window_start = today - timedelta(days=14)

        # Fetch 14-day intake history with ingredient names
        history_query = (
            select(NutritionIntake)
            .options(selectinload(NutritionIntake.ingredient))
            .where(
                NutritionIntake.user_id == user_id,
                NutritionIntake.day_date >= window_start,
            )
            .order_by(NutritionIntake.day_date.desc(), NutritionIntake.created_at.desc())
        )
        result = await self.session.execute(history_query)
        intakes = result.scalars().all()

        if not intakes:
            return []

        # Build history text
        history_lines = []
        for intake in intakes:
            name = intake.ingredient.name if intake.ingredient else "Unknown"
            history_lines.append(
                f"- {intake.day_date} | {name} | {intake.quantity} {intake.unit} | id:{intake.ingredient_id}"
            )
        intake_history = "\n".join(history_lines[:100])

        # Build frequency summary
        freq_query = (
            select(
                NutritionIntake.ingredient_id,
                NutritionIngredient.name,
                func.count().label("count"),
                func.max(NutritionIntake.day_date).label("last_logged"),
            )
            .join(NutritionIngredient, NutritionIntake.ingredient_id == NutritionIngredient.id)
            .where(
                NutritionIntake.user_id == user_id,
                NutritionIntake.day_date >= window_start,
            )
            .group_by(NutritionIntake.ingredient_id, NutritionIngredient.name)
            .order_by(func.count().desc())
            .limit(30)
        )
        freq_result = await self.session.execute(freq_query)
        freq_rows = freq_result.all()

        frequency_lines = []
        for row in freq_rows:
            frequency_lines.append(
                f"- {row.name} (id:{row.ingredient_id}): {row.count}x in 14d, last on {row.last_logged}"
            )
        frequency_summary = "\n".join(frequency_lines) or "No history yet."

        # Today's menu
        todays_intakes = [i for i in intakes if i.day_date == today]
        if todays_intakes:
            todays_menu = ", ".join(
                f"{i.ingredient.name} ({i.quantity} {i.unit})"
                for i in todays_intakes
                if i.ingredient
            )
        else:
            todays_menu = "Nothing logged yet today."

        # Time of day
        hour = now.hour
        if hour < 11:
            time_of_day = "morning (breakfast time)"
        elif hour < 14:
            time_of_day = "midday (lunch time)"
        elif hour < 17:
            time_of_day = "afternoon (snack time)"
        else:
            time_of_day = "evening (dinner time)"

        prompt = NUTRITION_SUGGESTION_PROMPT.format(
            time_of_day=time_of_day,
            todays_menu=todays_menu,
            intake_history=intake_history,
            frequency_summary=frequency_summary,
        )

        try:
            result = await self.client.generate_json(
                prompt,
                response_model=NutritionSuggestionOutput,
            )
        except Exception as exc:
            logger.error("[llm-fallback] nutrition_suggestion_agent._generate failed: {}", exc)
            return []

        return [item.model_dump() for item in result.data.suggestions[:10]]
