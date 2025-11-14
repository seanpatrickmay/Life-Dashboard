"""Manual Garmin ingestion + Vertex insight refresh."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from datetime import timedelta
from typing import Any, Mapping, Sequence

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

LOG_LEVEL = os.getenv("MANUAL_INGEST_LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(sys.stdout, level="WARNING")
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    filter=lambda record: record["extra"].get("component") == "manual_ingest",
)
log = logger.bind(component="manual_ingest")

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
from app.services.nutrition_goals_service import NutritionGoalsService  # type: ignore  # noqa: E402
from app.utils.timezone import eastern_now, eastern_today  # type: ignore  # noqa: E402


async def main() -> None:
    garmin = GarminClient()
    garmin.authenticate()
    lookback_days = 30
    today = eastern_today()
    start_date = today - timedelta(days=lookback_days - 1)
    cutoff_dt = eastern_now() - timedelta(days=lookback_days)

    activities = garmin.fetch_recent_activities(cutoff_dt)
    hrv_payload = garmin.fetch_daily_hrv(start_date, today)
    rhr_payload = garmin.fetch_daily_rhr(start_date, today)
    sleep_payload = garmin.fetch_sleep(start_date, today)
    load_payload = garmin.fetch_training_loads(start_date, today)
    energy_payload = garmin.fetch_daily_energy(start_date, today)

    log.info(
        "Garmin fetch totals — activities: {}, HRV: {}, RHR: {}, sleep: {}, training load: {}, energy: {}",
        len(activities),
        len(hrv_payload),
        len(rhr_payload),
        len(sleep_payload),
        len(load_payload),
        len(energy_payload),
    )

    def has_valid_data(payload: Any) -> bool:
        if payload is None:
            return False
        if isinstance(payload, Mapping):
            return any(value is not None for value in payload.values())
        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
            return any(item is not None for item in payload)
        return bool(payload)

    payloads = {
        "activities": activities,
        "hrv": hrv_payload,
        "rhr": rhr_payload,
        "sleep": sleep_payload,
        "training load": load_payload,
        "energy": energy_payload,
    }
    missing_sources = [label for label, payload in payloads.items() if not has_valid_data(payload)]
    if missing_sources:
        log.debug("Garmin fetch returned no valid data for {}", ", ".join(missing_sources))

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
            energy_payload=energy_payload,
        )
        log.info("Metrics ingest summary: {}", summary)
        goals = NutritionGoalsService(session)
        await goals.recompute_goals(user_id=1)
        await session.commit()
        await insight.refresh_daily_insight(user_id=1)


if __name__ == "__main__":
    asyncio.run(main())
