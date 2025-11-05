"""Manual Garmin ingestion + Vertex insight refresh."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

host_db_url = os.getenv("DATABASE_URL_HOST")
if host_db_url:
    os.environ["DATABASE_URL"] = host_db_url

sys.path.append(str(ROOT / "backend"))

from sqlalchemy import text

from app.clients.garmin_client import GarminClient  # type: ignore  # noqa: E402
from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402
from app.db.models.entities import User  # type: ignore  # noqa: E402
from app.services.insight_service import InsightService  # type: ignore  # noqa: E402
from app.services.metrics_service import MetricsService  # type: ignore  # noqa: E402


async def main() -> None:
    garmin = GarminClient()
    garmin.authenticate()
    lookback_days = 30
    today = date.today()
    start_date = today - timedelta(days=lookback_days - 1)
    cutoff_dt = datetime.utcnow() - timedelta(days=lookback_days)

    activities = garmin.fetch_recent_activities(cutoff_dt)
    hrv_payload = garmin.fetch_daily_hrv(start_date, today)
    rhr_payload = garmin.fetch_daily_rhr(start_date, today)
    sleep_payload = garmin.fetch_sleep(start_date, today)
    load_payload = garmin.fetch_training_loads(start_date, today)

    logger.info(
        "Garmin fetch totals — activities: {}, HRV: {}, RHR: {}, sleep: {}, training load: {}",
        len(activities),
        len(hrv_payload),
        len(rhr_payload),
        len(sleep_payload),
        len(load_payload),
    )

    def preview(label: str, payload: object) -> None:
        if not payload:
            logger.info("No {} entries fetched.", label)
            return
        if isinstance(payload, list):
            sample = payload[: min(len(payload), 3)]
        else:
            sample = payload
        logger.info("Sample {} payload: {}", label, sample)

    preview("activities", activities)
    preview("hrv", hrv_payload)
    preview("rhr", rhr_payload)
    preview("sleep", sleep_payload)
    preview("training load", load_payload)

    async with AsyncSessionLocal() as session:
        await session.execute(text("ALTER TABLE IF EXISTS activity ALTER COLUMN garmin_id TYPE BIGINT"))
        await session.execute(text("ALTER TABLE IF EXISTS vertexinsight ALTER COLUMN prompt TYPE TEXT"))
        await session.execute(text("ALTER TABLE IF EXISTS vertexinsight ALTER COLUMN response_text TYPE TEXT"))
        existing_user = await session.get(User, 1)
        if existing_user is None:
            user = User(id=1, email="owner@example.com", display_name="Owner")
            session.add(user)
        await session.commit()
        metrics = MetricsService(session, garmin=garmin)
        insight = InsightService(session)
        summary = await metrics.ingest(
            user_id=1,
            lookback_days=lookback_days,
            activities=activities,
            hrv_payload=hrv_payload,
            rhr_payload=rhr_payload,
            sleep_payload=sleep_payload,
            load_payload=load_payload,
        )
        logger.info("Metrics ingest summary: {}", summary)
        await insight.refresh_daily_insight(user_id=1)


if __name__ == "__main__":
    asyncio.run(main())
