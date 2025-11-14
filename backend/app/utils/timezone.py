"""Helpers for working with US Eastern time."""
from __future__ import annotations

from datetime import datetime, date
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo("America/New_York")


def eastern_now() -> datetime:
    """Return the current time in US Eastern as an aware datetime."""
    return datetime.now(EASTERN_TZ)


def eastern_today() -> date:
    """Return today's date in US Eastern."""
    return eastern_now().date()
