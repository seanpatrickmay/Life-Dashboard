"""Helpers for working with US Eastern time."""
from __future__ import annotations

from datetime import date, datetime, timezone
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


def resolve_time_zone(time_zone: str | None) -> ZoneInfo:
    """Return a ZoneInfo for the provided time zone string, defaulting to UTC."""
    tz_name = (time_zone or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(tz_name)
    except Exception:  # pragma: no cover - defensive fallback
        return timezone.utc


def local_now(time_zone: str | None) -> datetime:
    """Return the current time for the provided time zone."""
    zone = resolve_time_zone(time_zone)
    return datetime.now(zone)


def local_today(time_zone: str | None) -> date:
    """Return today's date for the provided time zone."""
    return local_now(time_zone).date()


def to_naive_eastern(dt: datetime) -> datetime:
    """Return a timezone-naive datetime representing Eastern time."""
    eastern = ensure_eastern(dt)
    return eastern.replace(tzinfo=None)
