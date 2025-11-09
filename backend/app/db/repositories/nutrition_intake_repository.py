from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.nutrition import (
    NutritionFood,
    NutritionIntake,
    NutritionIntakeSource,
)


class NutritionIntakeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_intake(
        self,
        *,
        user_id: int,
        food_id: int,
        quantity: float,
        unit: str,
        day: date,
        source: NutritionIntakeSource,
        claude_request_id: str | None = None,
    ) -> NutritionIntake:
        intake = NutritionIntake(
            user_id=user_id,
            food_id=food_id,
            quantity=quantity,
            unit=unit,
            day_date=day,
            source=source,
            claude_request_id=claude_request_id,
        )
        self.session.add(intake)
        return intake

    async def fetch_for_date(self, user_id: int, day: date) -> list[NutritionIntake]:
        stmt = (
            select(NutritionIntake)
            .where(NutritionIntake.user_id == user_id, NutritionIntake.day_date == day)
            .options(selectinload(NutritionIntake.food).selectinload(NutritionFood.profile))
            .order_by(NutritionIntake.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def fetch_between(self, user_id: int, start: date, end: date) -> list[NutritionIntake]:
        stmt = (
            select(NutritionIntake)
            .where(
                NutritionIntake.user_id == user_id,
                NutritionIntake.day_date >= start,
                NutritionIntake.day_date <= end,
            )
            .options(selectinload(NutritionIntake.food).selectinload(NutritionFood.profile))
            .order_by(NutritionIntake.day_date.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def fetch_for_day_with_food(
        self, user_id: int, day: date
    ) -> list[NutritionIntake]:
        stmt = (
            select(NutritionIntake)
            .where(NutritionIntake.user_id == user_id, NutritionIntake.day_date == day)
            .options(
                selectinload(NutritionIntake.food).selectinload(
                    NutritionFood.profile
                )
            )
            .order_by(NutritionIntake.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def update_quantity(
        self, intake_id: int, *, quantity: float, unit: str
    ) -> NutritionIntake | None:
        stmt = (
            select(NutritionIntake)
            .where(NutritionIntake.id == intake_id)
            .options(selectinload(NutritionIntake.food))
        )
        result = await self.session.execute(stmt)
        intake = result.scalar_one_or_none()
        if intake is None:
            return None
        intake.quantity = quantity
        intake.unit = unit
        return intake

    async def delete_intake(self, intake_id: int) -> None:
        stmt = delete(NutritionIntake).where(NutritionIntake.id == intake_id)
        await self.session.execute(stmt)
