"""Tests for Garmin fetch optimizations: range building, change detection, concurrency."""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import get_settings
get_settings.cache_clear()

import pytest
from app.services.metrics_service import MetricsService


def _run(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)


class TestBuildFetchRanges:
    """Unit tests for _build_fetch_ranges — the range collapsing logic."""

    def test_fresh_window_only_no_historical(self):
        """When no historical dates changed, only the fresh window is returned."""
        today = date(2026, 3, 20)
        fresh_start = today - timedelta(days=1)  # yesterday
        ranges = MetricsService._build_fetch_ranges(
            fresh_start=fresh_start,
            end_date=today,
            historical_dates=set(),
            earliest=today - timedelta(days=29),
        )
        assert ranges == [(date(2026, 3, 19), date(2026, 3, 20))]

    def test_single_historical_date_adds_separate_range(self):
        """A single historical date produces two ranges: historical + fresh."""
        today = date(2026, 3, 20)
        fresh_start = date(2026, 3, 19)
        ranges = MetricsService._build_fetch_ranges(
            fresh_start=fresh_start,
            end_date=today,
            historical_dates={date(2026, 3, 10)},
            earliest=date(2026, 2, 19),
        )
        assert len(ranges) == 2
        assert ranges[0] == (date(2026, 3, 10), date(2026, 3, 10))
        assert ranges[1] == (date(2026, 3, 19), date(2026, 3, 20))

    def test_adjacent_historical_dates_merge(self):
        """Consecutive historical dates collapse into one range."""
        today = date(2026, 3, 20)
        fresh_start = date(2026, 3, 19)
        ranges = MetricsService._build_fetch_ranges(
            fresh_start=fresh_start,
            end_date=today,
            historical_dates={date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)},
            earliest=date(2026, 2, 19),
        )
        assert len(ranges) == 2
        assert ranges[0] == (date(2026, 3, 10), date(2026, 3, 12))
        assert ranges[1] == (date(2026, 3, 19), date(2026, 3, 20))

    def test_historical_adjacent_to_fresh_merges(self):
        """A historical date right before fresh_start merges into one range."""
        today = date(2026, 3, 20)
        fresh_start = date(2026, 3, 19)
        ranges = MetricsService._build_fetch_ranges(
            fresh_start=fresh_start,
            end_date=today,
            historical_dates={date(2026, 3, 18)},
            earliest=date(2026, 2, 19),
        )
        assert ranges == [(date(2026, 3, 18), date(2026, 3, 20))]

    def test_multiple_scattered_historical_dates(self):
        """Non-adjacent historical dates produce separate ranges."""
        today = date(2026, 3, 20)
        fresh_start = date(2026, 3, 19)
        ranges = MetricsService._build_fetch_ranges(
            fresh_start=fresh_start,
            end_date=today,
            historical_dates={date(2026, 3, 5), date(2026, 3, 12)},
            earliest=date(2026, 2, 19),
        )
        assert len(ranges) == 3
        assert ranges[0] == (date(2026, 3, 5), date(2026, 3, 5))
        assert ranges[1] == (date(2026, 3, 12), date(2026, 3, 12))
        assert ranges[2] == (date(2026, 3, 19), date(2026, 3, 20))

    def test_empty_when_no_dates(self):
        """Edge case: fresh_start > end_date and no historical → empty."""
        ranges = MetricsService._build_fetch_ranges(
            fresh_start=date(2026, 3, 21),
            end_date=date(2026, 3, 20),
            historical_dates=set(),
            earliest=date(2026, 2, 19),
        )
        assert ranges == []


class TestDetectChangedHistoricalDates:
    """Tests for the activity-based change detection."""

    def test_no_new_activities_returns_empty(self):
        session = AsyncMock()
        service = MetricsService(session)
        service.activity_repo = AsyncMock()
        service.activity_repo.get_known_garmin_ids = AsyncMock(return_value={100, 200, 300})

        activities = [
            {"activityId": 100, "startTimeLocal": "2026-03-10T08:00:00"},
            {"activityId": 200, "startTimeLocal": "2026-03-15T08:00:00"},
        ]
        result = _run(service._detect_changed_historical_dates(
            user_id=1,
            activities=activities,
            history_start=date(2026, 2, 19),
            history_end=date(2026, 3, 17),
        ))
        assert result == set()

    def test_new_activity_in_history_detected(self):
        session = AsyncMock()
        service = MetricsService(session)
        service.activity_repo = AsyncMock()
        service.activity_repo.get_known_garmin_ids = AsyncMock(return_value={100})

        activities = [
            {"activityId": 100, "startTimeLocal": "2026-03-10T08:00:00"},
            {"activityId": 999, "startTimeLocal": "2026-03-12T08:00:00"},  # new!
        ]
        result = _run(service._detect_changed_historical_dates(
            user_id=1,
            activities=activities,
            history_start=date(2026, 2, 19),
            history_end=date(2026, 3, 17),
        ))
        assert result == {date(2026, 3, 12)}

    def test_new_activity_in_fresh_window_ignored(self):
        """Activities in the fresh window aren't flagged as historical changes."""
        session = AsyncMock()
        service = MetricsService(session)
        service.activity_repo = AsyncMock()
        service.activity_repo.get_known_garmin_ids = AsyncMock(return_value=set())

        activities = [
            {"activityId": 999, "startTimeLocal": "2026-03-20T08:00:00"},  # today = fresh
        ]
        result = _run(service._detect_changed_historical_dates(
            user_id=1,
            activities=activities,
            history_start=date(2026, 2, 19),
            history_end=date(2026, 3, 17),  # fresh starts 3/19
        ))
        assert result == set()


class TestThrottledCallThreadSafety:
    """Verify the threading lock prevents concurrent Garmin API calls."""

    def test_lock_serializes_calls(self):
        """Calls from multiple threads should not overlap."""
        from app.clients.garmin_client import GarminClient

        call_log: list[tuple[str, float, float]] = []
        lock = threading.Lock()

        def mock_api_call(name: str):
            start = time.monotonic()
            time.sleep(0.05)  # simulate API latency
            end = time.monotonic()
            with lock:
                call_log.append((name, start, end))
            return {"ok": True}

        client = GarminClient.__new__(GarminClient)
        client._api_lock = threading.Lock()
        client.client = MagicMock()

        from app.clients.garmin_client import _CALL_DELAY
        # Temporarily reduce delay for test speed
        with patch("app.clients.garmin_client._CALL_DELAY", 0.01):
            threads = []
            for i in range(3):
                t = threading.Thread(
                    target=client._throttled_call,
                    args=(lambda n=f"call_{i}": mock_api_call(n),),
                )
                threads.append(t)

            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert len(call_log) == 3
        # Verify no overlapping: each call's start should be >= previous call's end
        sorted_calls = sorted(call_log, key=lambda x: x[1])
        for i in range(1, len(sorted_calls)):
            prev_end = sorted_calls[i - 1][2]
            curr_start = sorted_calls[i][1]
            assert curr_start >= prev_end - 0.001, (
                f"Calls overlapped: {sorted_calls[i-1]} and {sorted_calls[i]}"
            )
