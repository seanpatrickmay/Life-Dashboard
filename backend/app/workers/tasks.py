"""Background task controllers for visit-triggered ingestion.

Controllers are now DB-backed (via the job_run table) so throttle state
survives across stateless Lambda invocations.  Work is dispatched through
JobQueue (InlineJobQueue by default; SqsJobQueue in Lambda Phase 2) so
the same handler body runs both inline and in the worker Lambda.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.job_run import JobRun
from app.db.session import AsyncSessionLocal
from app.jobs.queue import get_job_queue
from app.jobs.registry import job
from app.services.insight_service import InsightService
from app.services.metrics_service import MetricsService
from app.services.nutrition_goals_service import NutritionGoalsService
from app.utils.timezone import eastern_now, eastern_today, ensure_eastern

INSIGHT_FIELDS = {"hrv_avg_ms", "rhr_bpm", "sleep_seconds"}

_VISIT_COOLDOWN = timedelta(minutes=30)
_DIGEST_COOLDOWN = timedelta(hours=6)

# Maximum time a job is expected to run. If running=True but last_started_at is
# older than this threshold the lock is assumed stale (worker crashed before
# finalizing). Lambda max execution time is 15 min; this is intentionally larger.
STALE_LOCK_TIMEOUT = timedelta(minutes=30)


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


# ---------------------------------------------------------------------------
# Helper: load or create a JobRun row
# ---------------------------------------------------------------------------

async def _get_or_create_job_run(session: AsyncSession, job_name: str) -> JobRun:
    """Load the JobRun for *job_name*, creating it (with defaults) if absent."""
    result = await session.execute(
        select(JobRun).where(JobRun.id == job_name).with_for_update()
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = JobRun(id=job_name, running=False)
        session.add(row)
        await session.flush()
    return row


def _build_status(row: JobRun, *, job_started: bool, cooldown: timedelta, message: str) -> RefreshJobStatus:
    return RefreshJobStatus(
        job_started=job_started,
        running=row.running,
        last_started_at=row.last_started_at,
        last_completed_at=row.last_completed_at,
        next_allowed_at=row.next_allowed_at,
        cooldown_seconds=int(cooldown.total_seconds()),
        message=message,
        last_error=row.last_error,
    )


# ---------------------------------------------------------------------------
# Job handlers (registered with @job so InlineJobQueue and SqsJobQueue both run them)
# ---------------------------------------------------------------------------

async def run_metrics_refresh(session: AsyncSession, user_id: int, lookback_days: int) -> None:
    """Core metrics/goals/insight pipeline shared by job handlers and scheduled Lambda.

    Runs ingest → recompute_goals → commit → (conditional) refresh_daily_insight.
    The *session* is managed by the caller; this function does NOT open or close it.
    """
    metrics = MetricsService(session)
    insight = InsightService(session)
    goals = NutritionGoalsService(session)
    summary = await metrics.ingest(user_id=user_id, lookback_days=lookback_days)
    await goals.recompute_goals(user_id=user_id)
    await session.commit()
    if _should_refresh_insight(summary):
        await insight.refresh_daily_insight(user_id=user_id)


@job("visit_refresh")
async def _handle_visit_refresh(payload: dict) -> None:
    """Run the visit-triggered metrics/goals/insight pipeline."""
    user_id: int = payload["user_id"]
    error: str | None = None
    try:
        async with AsyncSessionLocal() as session:
            await run_metrics_refresh(session, user_id=user_id, lookback_days=14)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Visit-triggered refresh failed: {}", exc)
        error = str(exc)
    finally:
        await _finalize_job_run("visit_refresh", error=error, cooldown=_VISIT_COOLDOWN)


@job("digest_refresh")
async def _handle_digest_refresh(payload: dict) -> None:  # noqa: ARG001
    """Run the AI Digest pipeline."""
    error: str | None = None
    try:
        async with AsyncSessionLocal() as session:
            from app.services.ai_digest_service import AIDigestService
            service = AIDigestService(session)
            await service.run_pipeline()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Digest refresh failed: {}", exc)
        error = str(exc)
    finally:
        await _finalize_job_run("digest_refresh", error=error, cooldown=_DIGEST_COOLDOWN)


async def _finalize_job_run(job_name: str, *, error: str | None, cooldown: timedelta) -> None:
    """Mark the JobRun as complete (or failed) and advance next_allowed_at."""
    try:
        async with AsyncSessionLocal() as session:
            row = await _get_or_create_job_run(session, job_name)
            row.running = False
            row.last_completed_at = eastern_now()
            row.next_allowed_at = eastern_now() + cooldown
            if error is not None:
                row.last_error = error
            await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to finalize job_run row for {}", job_name)


# ---------------------------------------------------------------------------
# Helpers shared between visit handler and legacy _should_refresh_insight
# ---------------------------------------------------------------------------

def _should_refresh_insight(summary: dict) -> bool:
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


# ---------------------------------------------------------------------------
# DB-backed controllers
# ---------------------------------------------------------------------------

class VisitRefreshController:
    """DB-backed throttled refresh controller for visit-triggered ingestion."""

    def __init__(self, *, cooldown: timedelta = _VISIT_COOLDOWN) -> None:
        self._cooldown = cooldown

    async def request_refresh(self, session: AsyncSession, *, user_id: int) -> RefreshJobStatus:
        now = eastern_now()
        row = await _get_or_create_job_run(session, "visit_refresh")

        if row.running:
            # Stale-lock recovery: if the worker crashed without finalizing, clear the lock.
            stale = (
                row.last_started_at is not None
                and now - ensure_eastern(row.last_started_at) > STALE_LOCK_TIMEOUT
            )
            if not stale:
                await session.commit()
                return _build_status(row, job_started=False, cooldown=self._cooldown, message="Refresh already running.")
            # Stale lock — fall through and reschedule
            logger.warning("visit_refresh stale lock detected (started {}); clearing.", row.last_started_at)
            row.running = False

        next_allowed = ensure_eastern(row.next_allowed_at) if row.next_allowed_at else None
        if next_allowed and now < next_allowed:
            await session.commit()
            return _build_status(row, job_started=False, cooldown=self._cooldown, message="Waiting for cooldown window.")

        row.running = True
        row.last_started_at = now
        row.last_error = None
        await session.commit()

        await get_job_queue().enqueue("visit_refresh", {"user_id": user_id})
        return _build_status(row, job_started=True, cooldown=self._cooldown, message="Refresh started.")


class DigestRefreshController:
    """DB-backed throttled refresh controller for the AI Digest pipeline."""

    def __init__(self, *, cooldown: timedelta = _DIGEST_COOLDOWN) -> None:
        self._cooldown = cooldown

    async def request_refresh(self, session: AsyncSession, *, force: bool = False) -> RefreshJobStatus:
        now = eastern_now()
        row = await _get_or_create_job_run(session, "digest_refresh")

        if row.running:
            # Stale-lock recovery: if the worker crashed without finalizing, clear the lock.
            stale = (
                row.last_started_at is not None
                and now - ensure_eastern(row.last_started_at) > STALE_LOCK_TIMEOUT
            )
            if not stale:
                await session.commit()
                return _build_status(row, job_started=False, cooldown=self._cooldown, message="Digest refresh already running.")
            # Stale lock — fall through and reschedule
            logger.warning("digest_refresh stale lock detected (started {}); clearing.", row.last_started_at)
            row.running = False

        next_allowed = ensure_eastern(row.next_allowed_at) if row.next_allowed_at else None
        if not force and next_allowed and now < next_allowed:
            await session.commit()
            return _build_status(row, job_started=False, cooldown=self._cooldown, message="Waiting for cooldown window.")

        row.running = True
        row.last_started_at = now
        row.last_error = None
        await session.commit()

        await get_job_queue().enqueue("digest_refresh", {})
        return _build_status(row, job_started=True, cooldown=self._cooldown, message="Digest refresh started.")


# ---------------------------------------------------------------------------
# Singletons / factory functions (unchanged public API)
# ---------------------------------------------------------------------------

_visit_refresh_controller: VisitRefreshController | None = None


def get_visit_refresh_controller() -> VisitRefreshController:
    global _visit_refresh_controller  # noqa: PLW0603
    if _visit_refresh_controller is None:
        _visit_refresh_controller = VisitRefreshController()
    return _visit_refresh_controller


_digest_refresh_controller: DigestRefreshController | None = None


def get_digest_refresh_controller() -> DigestRefreshController:
    global _digest_refresh_controller  # noqa: PLW0603
    if _digest_refresh_controller is None:
        _digest_refresh_controller = DigestRefreshController()
    return _digest_refresh_controller
