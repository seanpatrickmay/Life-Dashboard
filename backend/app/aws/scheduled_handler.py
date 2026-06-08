"""EventBridge scheduled Lambda handlers.

Two handlers:
- garmin_ingest  — metrics ingest + nutrition goals recompute + daily readiness insight
- rss_digest     — AI RSS digest pipeline

Each handler calls cold_start() (idempotent) then runs exactly one asyncio.run()
for the full async pipeline.  NullPool is active under LD_RUNTIME=aws, so connections
are created and closed within the single event loop per invocation.
"""
from __future__ import annotations

import asyncio

from loguru import logger

from app.aws.bootstrap import cold_start


def garmin_ingest(event: dict | None = None, context: object = None) -> dict:
    """EventBridge handler: Garmin metrics ingest + goals + readiness insight.

    EventBridge rule payload (optional overrides)::

        {"user_id": 1, "lookback_days": 30}
    """
    cold_start()
    event = event or {}
    user_id = int(event.get("user_id", 1))
    lookback_days = int(event.get("lookback_days", 30))
    asyncio.run(_run_garmin_ingest(user_id, lookback_days))
    return {"ok": True, "job": "garmin_ingest", "user_id": user_id}


def rss_digest(event: dict | None = None, context: object = None) -> dict:
    """EventBridge handler: AI RSS digest pipeline."""
    cold_start()
    asyncio.run(_run_rss_digest())
    return {"ok": True, "job": "rss_digest"}


# ---------------------------------------------------------------------------
# Async pipeline bodies
# ---------------------------------------------------------------------------

async def _run_garmin_ingest(user_id: int, lookback_days: int) -> None:
    """Run the full metrics/goals/insight pipeline inside a single event loop."""
    from app.db.session import get_sessionmaker
    from app.workers.tasks import run_metrics_refresh

    try:
        async with get_sessionmaker()() as session:
            await run_metrics_refresh(session, user_id=user_id, lookback_days=lookback_days)
    except Exception as exc:
        logger.exception("garmin_ingest pipeline failed: {}", exc)
        raise


async def _run_rss_digest() -> None:
    """Run the AI digest pipeline inside a single event loop."""
    from app.db.session import get_sessionmaker
    from app.services.ai_digest_service import AIDigestService

    try:
        async with get_sessionmaker()() as session:
            await AIDigestService(session).run_pipeline()
    except Exception as exc:
        logger.exception("rss_digest pipeline failed: {}", exc)
        raise
