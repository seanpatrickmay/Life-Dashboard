"""Activity persistence helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import Activity
from app.utils.timezone import ensure_eastern, to_naive_eastern
from loguru import logger


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_many(self, user_id: int, activities: Iterable[dict]) -> int:
        count = 0
        for payload in activities:
            garmin_id = int(payload["activityId"])
            stmt = select(Activity).where(Activity.garmin_id == garmin_id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            start_time = self._parse_start(payload)
            start_time_naive = to_naive_eastern(start_time)
            if existing:
                existing.start_time = start_time_naive
                existing.duration_sec = float(payload.get("duration", 0))
                existing.distance_m = float(payload.get("distance", 0))
                existing.calories = float(payload.get("calories") or 0)
                existing.raw_payload = payload
                logger.info(
                    "Activity updated in DB (id={}, garmin_id={}, name='{}', type={}, start={})",
                    existing.id,
                    garmin_id,
                    existing.name,
                    existing.type,
                    existing.start_time,
                )
            else:
                activity = Activity(
                    user_id=user_id,
                    garmin_id=garmin_id,
                    name=payload.get("activityName"),
                    type=self._activity_type(payload),
                    start_time=start_time_naive,
                    duration_sec=float(payload.get("duration", 0)),
                    distance_m=float(payload.get("distance", 0)),
                    calories=float(payload.get("calories") or 0),
                    raw_payload=payload,
                )
                self.session.add(activity)
                logger.info(
                    "Activity inserted into DB (garmin_id={}, name='{}', type={}, start={})",
                    garmin_id,
                    activity.name,
                    activity.type,
                    activity.start_time,
                )
            count += 1
        return count

    async def purge_all(self) -> None:
        await self.session.execute(delete(Activity))

    def _parse_start(self, payload: dict) -> datetime:
        from dateutil import parser

        timestamp = payload.get("startTimeLocal") or payload.get("startTimeGMT")
        parsed = parser.isoparse(timestamp)
        return ensure_eastern(parsed)

    def _activity_type(self, payload: dict) -> str | None:
        activity_type = payload.get("activityType")
        if isinstance(activity_type, dict):
            return activity_type.get("typeKey")
        return activity_type
