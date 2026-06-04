"""Tests for the EventBridge scheduled Lambda handlers.

Covers:
1. garmin_ingest handler: cold_start called, run_metrics_refresh invoked with correct
   user_id and lookback_days, handler returns {"ok": True, ...}.
2. rss_digest handler: cold_start called, AIDigestService.run_pipeline awaited once,
   handler returns {"ok": True, ...}.
3. asyncio.run is called exactly once per handler (the pipeline coroutine completes).
4. Pipeline exceptions propagate (handler re-raises after logging).
5. No real DB or network — all service boundaries are monkeypatched.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import app.aws.scheduled_handler as sh

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal async context-manager session double."""

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


def _fake_get_sessionmaker() -> object:
    """Returns a callable that produces _FakeSession instances."""
    class _SM:
        def __call__(self) -> _FakeSession:
            return _FakeSession()
    return _SM()


# ---------------------------------------------------------------------------
# garmin_ingest
# ---------------------------------------------------------------------------


class TestGarminIngestHandler:
    def test_returns_ok_with_default_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sh, "cold_start", lambda: None)
        refresh_mock = AsyncMock()
        monkeypatch.setattr(sh, "_run_garmin_ingest", refresh_mock)

        result = sh.garmin_ingest({})

        assert result == {"ok": True, "job": "garmin_ingest", "user_id": 1}
        refresh_mock.assert_awaited_once_with(1, 30)

    def test_reads_user_id_and_lookback_from_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sh, "cold_start", lambda: None)
        refresh_mock = AsyncMock()
        monkeypatch.setattr(sh, "_run_garmin_ingest", refresh_mock)

        result = sh.garmin_ingest({"user_id": 7, "lookback_days": 14})

        assert result["user_id"] == 7
        assert result["ok"] is True
        refresh_mock.assert_awaited_once_with(7, 14)

    def test_cold_start_called_before_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        call_order: list[str] = []

        monkeypatch.setattr(sh, "cold_start", lambda: call_order.append("cold_start"))

        async def _fake_ingest(user_id: int, lookback_days: int) -> None:
            call_order.append("pipeline")

        monkeypatch.setattr(sh, "_run_garmin_ingest", _fake_ingest)

        sh.garmin_ingest({"user_id": 1})

        assert call_order == ["cold_start", "pipeline"]

    def test_pipeline_exception_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sh, "cold_start", lambda: None)

        async def _failing_ingest(user_id: int, lookback_days: int) -> None:
            raise RuntimeError("network error")

        monkeypatch.setattr(sh, "_run_garmin_ingest", _failing_ingest)

        with pytest.raises(RuntimeError, match="network error"):
            sh.garmin_ingest({"user_id": 1})

    def test_asyncio_run_called_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """asyncio.run must be invoked exactly once per handler call."""
        monkeypatch.setattr(sh, "cold_start", lambda: None)

        run_call_count = 0
        original_run = asyncio.run

        def _counting_run(coro: object) -> object:
            nonlocal run_call_count
            run_call_count += 1
            return original_run(coro)

        monkeypatch.setattr(sh.asyncio, "run", _counting_run)
        monkeypatch.setattr(sh, "_run_garmin_ingest", AsyncMock())

        sh.garmin_ingest({"user_id": 1})
        assert run_call_count == 1

    def test_none_event_treated_as_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sh, "cold_start", lambda: None)
        refresh_mock = AsyncMock()
        monkeypatch.setattr(sh, "_run_garmin_ingest", refresh_mock)

        result = sh.garmin_ingest(None)

        assert result["user_id"] == 1
        refresh_mock.assert_awaited_once_with(1, 30)


# ---------------------------------------------------------------------------
# _run_garmin_ingest (async integration: session + run_metrics_refresh)
# ---------------------------------------------------------------------------


class TestRunGarminIngestAsync:
    def test_calls_run_metrics_refresh_with_correct_args(self) -> None:
        """_run_garmin_ingest passes session, user_id, lookback_days to run_metrics_refresh."""
        refresh_calls: list[tuple] = []

        async def _fake_refresh(session: object, user_id: int, lookback_days: int) -> None:
            refresh_calls.append((user_id, lookback_days))

        with (
            patch("app.db.session.get_sessionmaker", _fake_get_sessionmaker),
            patch("app.workers.tasks.run_metrics_refresh", _fake_refresh),
        ):
            asyncio.run(sh._run_garmin_ingest(user_id=7, lookback_days=21))

        assert refresh_calls == [(7, 21)]

    def test_exception_is_reraised(self) -> None:
        async def _bad_refresh(*args: object, **kwargs: object) -> None:
            raise ValueError("ingest fail")

        with (
            patch("app.db.session.get_sessionmaker", _fake_get_sessionmaker),
            patch("app.workers.tasks.run_metrics_refresh", _bad_refresh),
        ):
            with pytest.raises(ValueError, match="ingest fail"):
                asyncio.run(sh._run_garmin_ingest(user_id=1, lookback_days=30))


# ---------------------------------------------------------------------------
# rss_digest
# ---------------------------------------------------------------------------


class TestRssDigestHandler:
    def test_returns_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sh, "cold_start", lambda: None)
        digest_mock = AsyncMock()
        monkeypatch.setattr(sh, "_run_rss_digest", digest_mock)

        result = sh.rss_digest({})

        assert result == {"ok": True, "job": "rss_digest"}
        digest_mock.assert_awaited_once()

    def test_cold_start_called_before_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        call_order: list[str] = []
        monkeypatch.setattr(sh, "cold_start", lambda: call_order.append("cold_start"))

        async def _fake_digest() -> None:
            call_order.append("pipeline")

        monkeypatch.setattr(sh, "_run_rss_digest", _fake_digest)

        sh.rss_digest({})
        assert call_order == ["cold_start", "pipeline"]

    def test_pipeline_exception_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sh, "cold_start", lambda: None)

        async def _failing_digest() -> None:
            raise RuntimeError("feed error")

        monkeypatch.setattr(sh, "_run_rss_digest", _failing_digest)

        with pytest.raises(RuntimeError, match="feed error"):
            sh.rss_digest({})

    def test_asyncio_run_called_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sh, "cold_start", lambda: None)

        run_call_count = 0
        original_run = asyncio.run

        def _counting_run(coro: object) -> object:
            nonlocal run_call_count
            run_call_count += 1
            return original_run(coro)

        monkeypatch.setattr(sh.asyncio, "run", _counting_run)
        monkeypatch.setattr(sh, "_run_rss_digest", AsyncMock())

        sh.rss_digest({})
        assert run_call_count == 1

    def test_none_event_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sh, "cold_start", lambda: None)
        digest_mock = AsyncMock()
        monkeypatch.setattr(sh, "_run_rss_digest", digest_mock)

        result = sh.rss_digest(None)
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# _run_rss_digest (async integration: session + AIDigestService)
# ---------------------------------------------------------------------------


class TestRunRssDigestAsync:
    def test_awaits_run_pipeline_once(self) -> None:
        """_run_rss_digest creates a session and awaits AIDigestService.run_pipeline()."""
        pipeline_call_count = 0

        class _FakeDigestService:
            def __init__(self, session: object) -> None:
                pass

            async def run_pipeline(self) -> int:
                nonlocal pipeline_call_count
                pipeline_call_count += 1
                return 0

        with (
            patch("app.db.session.get_sessionmaker", _fake_get_sessionmaker),
            patch("app.services.ai_digest_service.AIDigestService", _FakeDigestService),
        ):
            asyncio.run(sh._run_rss_digest())

        assert pipeline_call_count == 1

    def test_exception_is_reraised(self) -> None:
        class _BadDigestService:
            def __init__(self, session: object) -> None:
                pass

            async def run_pipeline(self) -> int:
                raise RuntimeError("digest boom")

        with (
            patch("app.db.session.get_sessionmaker", _fake_get_sessionmaker),
            patch("app.services.ai_digest_service.AIDigestService", _BadDigestService),
        ):
            with pytest.raises(RuntimeError, match="digest boom"):
                asyncio.run(sh._run_rss_digest())
