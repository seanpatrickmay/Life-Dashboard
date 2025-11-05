from __future__ import annotations

from datetime import date


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current = current.fromordinal(current.toordinal() + 1)
