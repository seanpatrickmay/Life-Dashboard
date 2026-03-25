"""Shared date-parsing helpers."""
from __future__ import annotations

from datetime import date, datetime


def parse_iso_date(value: str | None) -> date | None:
    """Parse a date string in ISO format, returning None on failure.

    Handles both full ISO-8601 datetime strings (with optional timezone)
    and plain ``YYYY-MM-DD`` date strings.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
