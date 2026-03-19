from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.db.session import get_session, AsyncSessionLocal
from app.db.models.entities import User
from app.schemas.insights import InsightResponse
from app.services.insight_service import InsightService
from app.utils.timezone import EASTERN_TZ, eastern_now, eastern_today

router = APIRouter(prefix="/insights", tags=["insights"])


def _extract_pillar_from_narrative(narrative: str | None, pillar_name: str) -> tuple[float | None, str | None]:
    """Extract a pillar score and note from the stored narrative JSON."""
    if not narrative:
        return None, None
    try:
        data = json.loads(narrative)
    except (json.JSONDecodeError, TypeError):
        return None, None
    pillar = data.get(pillar_name)
    if not isinstance(pillar, dict):
        return None, None
    score = pillar.get("score")
    note = pillar.get("insight")
    try:
        score = float(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    return score, note if isinstance(note, str) else None


async def _background_refresh_insight(user_id: int) -> None:
    """Refresh the daily insight in the background when stale."""
    try:
        async with AsyncSessionLocal() as session:
            service = InsightService(session)
            await service.refresh_daily_insight(user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Background insight refresh failed: {}", exc)


@router.get("/daily", response_model=InsightResponse)
async def latest_insight(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InsightResponse:
    service = InsightService(session)
    metric = await service.fetch_latest_completed_metric(current_user.id)

    if metric is None:
        now = eastern_now()
        background_tasks.add_task(_background_refresh_insight, current_user.id)
        return InsightResponse(
            metric_date=now,
            readiness_score=None,
            readiness_label="Pending",
            narrative="Insight not yet generated.",
            source_model=settings.openai_model_name,
            last_updated=now,
            refreshing=True,
        )

    # Auto-trigger background refresh if insight is stale (older than today)
    today = eastern_today()
    is_stale = metric.metric_date < today
    if is_stale:
        background_tasks.add_task(_background_refresh_insight, current_user.id)

    insight = metric.readiness_insight
    source_model = insight.model_name if insight else settings.openai_model_name
    metric_datetime = datetime.combine(metric.metric_date, datetime.min.time(), tzinfo=EASTERN_TZ)
    last_updated = insight.updated_at if insight else metric_datetime
    narrative = metric.readiness_narrative or "Insight not yet generated."
    logger.debug(
        "Serving insight (date={}, len={}):\n{}",
        metric.metric_date,
        len(narrative),
        narrative,
    )

    # Extract new pillars from narrative JSON (no DB migration needed)
    nutrition_score, nutrition_note = _extract_pillar_from_narrative(narrative, "nutrition")
    productivity_score, productivity_note = _extract_pillar_from_narrative(narrative, "productivity")

    return InsightResponse(
        metric_date=metric_datetime,
        readiness_score=metric.readiness_score,
        readiness_label=metric.readiness_label,
        narrative=narrative,
        source_model=source_model,
        last_updated=last_updated,
        refreshing=is_stale,
        greeting=metric.insight_greeting,
        hrv_value_ms=metric.insight_hrv_value,
        hrv_note=metric.insight_hrv_note,
        hrv_score=metric.insight_hrv_score,
        rhr_value_bpm=metric.insight_rhr_value,
        rhr_note=metric.insight_rhr_note,
        rhr_score=metric.insight_rhr_score,
        sleep_value_hours=metric.insight_sleep_value_hours,
        sleep_note=metric.insight_sleep_note,
        sleep_score=metric.insight_sleep_score,
        training_load_value=metric.insight_training_load_value,
        training_load_note=metric.insight_training_load_note,
        training_load_score=metric.insight_training_load_score,
        morning_note=metric.insight_morning_note,
        nutrition_score=nutrition_score,
        nutrition_note=nutrition_note,
        productivity_score=productivity_score,
        productivity_note=productivity_note,
    )
