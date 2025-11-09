from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

TIME_ZONE_NAME = "America/New_York"
TIME_ZONE = ZoneInfo(TIME_ZONE_NAME)

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
async def get_current_time() -> dict[str, object]:
    now = datetime.now(TIME_ZONE)
    hour_decimal = now.hour + now.minute / 60 + now.second / 3600
    return {
        "iso": now.isoformat(),
        "time_zone": TIME_ZONE_NAME,
        "hour_decimal": round(hour_decimal, 4),
        "moment": compute_moment(now.hour)
    }
