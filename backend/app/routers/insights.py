from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.insights import InsightResponse
from app.services.insight_service import InsightService

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/daily", response_model=InsightResponse)
async def latest_insight(session: AsyncSession = Depends(get_session)) -> InsightResponse:
    service = InsightService(session)
    metric = await service.fetch_latest_completed_metric()
    if metric is None:
        return InsightResponse(
            metric_date=datetime.utcnow(),
            readiness_score=None,
            readiness_label="Pending",
            narrative="Insight not yet generated.",
            source_model="vertex",
            last_updated=datetime.utcnow(),
            refreshing=True,
        )

    insight = metric.vertex_insight
    source_model = insight.model_name if insight else "vertex"
    last_updated = insight.updated_at if insight else datetime.combine(metric.metric_date, datetime.min.time())
    narrative = metric.readiness_narrative or "Insight not yet generated."
    logger.debug(
        "Serving insight (date={}, len={}):\n{}",
        metric.metric_date,
        len(narrative),
        narrative,
    )
    return InsightResponse(
        metric_date=datetime.combine(metric.metric_date, datetime.min.time()),
        readiness_score=metric.readiness_score,
        readiness_label=metric.readiness_label,
        narrative=narrative,
        source_model=source_model,
        last_updated=last_updated,
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
    )
