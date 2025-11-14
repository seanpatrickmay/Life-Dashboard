"""Scheduler wiring for daily ingestion + insight refresh."""
from __future__ import annotations

from datetime import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.insight_service import InsightService
from app.services.metrics_service import MetricsService
from app.services.nutrition_goals_service import NutritionGoalsService
from app.utils.timezone import EASTERN_TZ

_scheduler: AsyncIOScheduler | None = None


async def run_daily_job() -> None:
    async with AsyncSessionLocal() as session:
        metrics = MetricsService(session)
        insight = InsightService(session)
        goals = NutritionGoalsService(session)
        logger.info("Running scheduled ingestion + insight refresh")
        await metrics.ingest(user_id=1)
        await goals.recompute_goals(user_id=1)
        await session.commit()
        await insight.refresh_daily_insight(user_id=1)


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler  # noqa: PLW0603
    if _scheduler:
        return _scheduler
    scheduler = AsyncIOScheduler(timezone=EASTERN_TZ)
    scheduler.add_job(run_daily_job, "cron", hour=settings.ingestion_hour_local, minute=0, id="daily-ingest")
    scheduler.start()
    _scheduler = scheduler
    return scheduler
