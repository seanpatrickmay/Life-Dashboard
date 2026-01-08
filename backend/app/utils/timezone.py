"""Helpers for working with US Eastern time."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo("America/New_York")


def eastern_now() -> datetime:
    """Return the current time in US Eastern as an aware datetime."""
    return datetime.now(EASTERN_TZ)


def eastern_today() -> date:
    """Return today's date in US Eastern."""
    return eastern_now().date()


def ensure_eastern(dt: datetime) -> datetime:
    """Convert or tag a datetime as US Eastern."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=EASTERN_TZ)
    return dt.astimezone(EASTERN_TZ)


def eastern_midnight(day: date) -> datetime:
    """Return midnight Eastern for the provided date."""
    return datetime.combine(day, datetime.min.time(), tzinfo=EASTERN_TZ)


def to_naive_eastern(dt: datetime) -> datetime:
    """Return a timezone-naive datetime representing Eastern time."""
    eastern = ensure_eastern(dt)
    return eastern.replace(tzinfo=None)
