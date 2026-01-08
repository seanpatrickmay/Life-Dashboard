"""Background task controllers for visit-triggered ingestion."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger

from app.db.session import AsyncSessionLocal
from app.services.insight_service import InsightService
from app.services.metrics_service import MetricsService
from app.services.nutrition_goals_service import NutritionGoalsService
from app.utils.timezone import eastern_now, eastern_today

INSIGHT_FIELDS = {"hrv_avg_ms", "rhr_bpm", "sleep_seconds"}


@dataclass
class RefreshJobStatus:
    job_started: bool
    running: bool
    last_started_at: datetime | None
    last_completed_at: datetime | None
    next_allowed_at: datetime | None
    cooldown_seconds: int
    message: str | None = None
    last_error: str | None = None


class VisitRefreshController:
    """Coordinates throttled refresh tasks when a visit ping arrives."""

    def __init__(self, *, cooldown: timedelta) -> None:
        self._cooldown = cooldown
        self._lock = asyncio.Lock()
        self._running = False
        self._last_started_at: datetime | None = None
        self._last_completed_at: datetime | None = None
        self._next_allowed_at: datetime | None = None
        self._last_error: str | None = None
        self._task: asyncio.Task[None] | None = None

    async def request_refresh(self, *, user_id: int) -> RefreshJobStatus:
        async with self._lock:
            now = eastern_now()
            if self._running:
                return self._build_status(job_started=False, message="Refresh already running.")
            if self._next_allowed_at and now < self._next_allowed_at:
                return self._build_status(job_started=False, message="Waiting for cooldown window.")
            self._running = True
            self._last_started_at = now
            self._next_allowed_at = now + self._cooldown
            self._last_error = None
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_refresh(user_id=user_id))
            return self._build_status(job_started=True, message="Refresh started.")

    async def _run_refresh(self, *, user_id: int) -> None:
        try:
            async with AsyncSessionLocal() as session:
                metrics = MetricsService(session)
                insight = InsightService(session)
                goals = NutritionGoalsService(session)
                summary = await metrics.ingest(user_id=user_id, lookback_days=14)
                await goals.recompute_goals(user_id=user_id)
                await session.commit()
                if self._should_refresh_insight(summary):
                    await insight.refresh_daily_insight(user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Visit-triggered refresh failed: {}", exc)
            async with self._lock:
                self._last_error = str(exc)
        finally:
            async with self._lock:
                self._running = False
                self._last_completed_at = eastern_now()

    def _should_refresh_insight(self, summary: dict) -> bool:
        changes: dict | None = summary.get("metric_changes") if isinstance(summary, dict) else None
        if not changes:
            return False
        today_label = eastern_today().isoformat()
        day_changes = changes.get(today_label)
        if not day_changes:
            return False
        if isinstance(day_changes, list):
            return any(field in INSIGHT_FIELDS for field in day_changes)
        return False

    def _build_status(self, *, job_started: bool, message: str) -> RefreshJobStatus:
        return RefreshJobStatus(
            job_started=job_started,
            running=self._running,
            last_started_at=self._last_started_at,
            last_completed_at=self._last_completed_at,
            next_allowed_at=self._next_allowed_at,
            cooldown_seconds=int(self._cooldown.total_seconds()),
            message=message,
            last_error=self._last_error,
        )


_visit_refresh_controller: VisitRefreshController | None = None


def get_visit_refresh_controller() -> VisitRefreshController:
    global _visit_refresh_controller  # noqa: PLW0603
    if _visit_refresh_controller is None:
        _visit_refresh_controller = VisitRefreshController(cooldown=timedelta(minutes=5))
    return _visit_refresh_controller
