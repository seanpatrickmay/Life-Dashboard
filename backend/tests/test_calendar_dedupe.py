from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import os
import sys

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.schemas.calendar import CalendarEventResponse  # noqa: E402


def _ensure_required_env() -> None:
    os.environ["APP_ENV"] = "local"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://life_dashboard:life_dashboard@localhost:5432/life_dashboard"
    os.environ["ADMIN_EMAIL"] = "admin@example.com"
    os.environ["FRONTEND_URL"] = "http://localhost:3000"
    os.environ["GARMIN_PASSWORD_ENCRYPTION_KEY"] = "x" * 32
    os.environ["OPENAI_API_KEY"] = "test-openai-key"
    os.environ["READINESS_ADMIN_TOKEN"] = "test-token"
    os.environ["GOOGLE_CLIENT_ID_LOCAL"] = "test-client-id"
    os.environ["GOOGLE_CLIENT_SECRET_LOCAL"] = "test-client-secret"
    os.environ["GOOGLE_REDIRECT_URI_LOCAL"] = "http://localhost:8000/api/auth/google/callback"


_ensure_required_env()

calendar_module_path = backend_root / "app" / "routers" / "calendar.py"
spec = importlib.util.spec_from_file_location("calendar_router", calendar_module_path)
assert spec and spec.loader
calendar_router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calendar_router)


def _event(
    *,
    id: int,
    summary: str | None,
    start: datetime,
    end: datetime,
    is_all_day: bool = False,
    calendar_primary: bool = False,
    calendar_is_life_dashboard: bool = False,
    organizer_self: bool = False,
    ical_uid: str | None = None,
    todo_id: int | None = None,
) -> CalendarEventResponse:
    return CalendarEventResponse(
        id=id,
        todo_id=todo_id,
        calendar_google_id=f"cal-{id}",
        calendar_summary=f"Calendar {id}",
        calendar_primary=calendar_primary,
        calendar_is_life_dashboard=calendar_is_life_dashboard,
        google_event_id=f"evt-{id}",
        recurring_event_id=None,
        ical_uid=ical_uid,
        summary=summary,
        description=None,
        location=None,
        start_time=start,
        end_time=end,
        is_all_day=is_all_day,
        status=None,
        visibility=None,
        transparency=None,
        hangout_link=None,
        conference_link=None,
        organizer={"self": True} if organizer_self else None,
        attendees=None,
    )


def test_fuzzy_dedupe_prefers_primary_calendar_event() -> None:
    start = datetime(2026, 2, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, 15, 0, tzinfo=timezone.utc)

    outlook = _event(id=1, summary="Team Sync", start=start, end=end, calendar_primary=False)
    google = _event(
        id=2,
        summary="Team sync",
        start=start + timedelta(minutes=2),
        end=end + timedelta(minutes=2),
        calendar_primary=True,
    )

    deduped = calendar_router._dedupe_events([outlook, google])

    assert [event.id for event in deduped] == [2]


def test_fuzzy_dedupe_does_not_remove_events_far_apart() -> None:
    first = _event(
        id=1,
        summary="Standup",
        start=datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 2, 1, 9, 30, tzinfo=timezone.utc),
    )
    second = _event(
        id=2,
        summary="Standup",
        start=datetime(2026, 2, 1, 11, 0, tzinfo=timezone.utc),
        end=datetime(2026, 2, 1, 11, 30, tzinfo=timezone.utc),
    )

    deduped = calendar_router._dedupe_events([first, second])

    assert [event.id for event in deduped] == [1, 2]


def test_fuzzy_dedupe_handles_all_day_end_time_variants() -> None:
    start = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    end_midnight = datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)
    end_2359 = datetime(2026, 2, 1, 23, 59, tzinfo=timezone.utc)

    non_primary = _event(
        id=1,
        summary="Holiday",
        start=start,
        end=end_midnight,
        is_all_day=True,
        calendar_primary=False,
    )
    primary = _event(
        id=2,
        summary="Holiday",
        start=start,
        end=end_2359,
        is_all_day=True,
        calendar_primary=True,
    )

    deduped = calendar_router._dedupe_events([non_primary, primary])

    assert [event.id for event in deduped] == [2]


def test_fuzzy_dedupe_does_not_suppress_todo_linked_events() -> None:
    start = datetime(2026, 2, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, 15, 0, tzinfo=timezone.utc)

    todo_event = _event(
        id=1,
        summary="Gym",
        start=start,
        end=end,
        calendar_is_life_dashboard=True,
        todo_id=123,
    )
    normal_event = _event(
        id=2,
        summary="Gym",
        start=start + timedelta(minutes=1),
        end=end + timedelta(minutes=1),
        calendar_primary=True,
    )

    deduped = calendar_router._dedupe_events([todo_event, normal_event])

    assert [event.id for event in deduped] == [1, 2]
