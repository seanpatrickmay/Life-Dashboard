"""Activity persistence helpers."""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import Activity
from app.utils.timezone import ensure_eastern, to_naive_eastern
from loguru import logger


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_many(self, user_id: int, activities: Iterable[dict]) -> int:
        activity_list = list(activities)
        if not activity_list:
            return 0

        # Batch-fetch all existing activities by garmin_id in one query
        garmin_ids = [int(p["activityId"]) for p in activity_list]
        stmt = select(Activity).where(
            Activity.user_id == user_id,
            Activity.garmin_id.in_(garmin_ids),
        )
        result = await self.session.execute(stmt)
        existing_map: dict[int, Activity] = {
            a.garmin_id: a for a in result.scalars().all()
        }

        count = 0
        for payload in activity_list:
            garmin_id = int(payload["activityId"])
            existing = existing_map.get(garmin_id)
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

    async def get_known_garmin_ids(self, user_id: int, since: date) -> set[int]:
        """Return the set of garmin_id values we already have on or after *since*."""
        stmt = (
            select(Activity.garmin_id)
            .where(
                Activity.user_id == user_id,
                func.date(Activity.start_time) >= since,
            )
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result.all()}

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
