from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.db.models.entities import User
from app.utils.timezone import EASTERN_TZ

TIME_ZONE = EASTERN_TZ
TIME_ZONE_NAME = getattr(TIME_ZONE, "key", "America/New_York")

router = APIRouter(prefix="/time", tags=["time"])

Moment = str  # reuse frontend moment strings (morning/noon/twilight/night)


def compute_moment(hour: int) -> Moment:
    if 6 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "noon"
    if 17 <= hour < 21:
        return "twilight"
    return "night"


@router.get("/", summary="Current time in US Eastern")
async def get_current_time(current_user: User = Depends(get_current_user)) -> dict[str, object]:
    now = datetime.now(TIME_ZONE)
    hour_decimal = now.hour + now.minute / 60 + now.second / 3600
    return {
        "iso": now.isoformat(),
        "time_zone": TIME_ZONE_NAME,
        "hour_decimal": round(hour_decimal, 4),
        "moment": compute_moment(now.hour)
    }
