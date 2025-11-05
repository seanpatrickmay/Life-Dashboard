from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entities import DailyMetric, VertexInsight
from app.db.session import get_session
from app.schemas.insights import InsightResponse

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/daily", response_model=InsightResponse)
async def latest_insight(session: AsyncSession = Depends(get_session)) -> InsightResponse:
    metric_stmt = (
        select(DailyMetric)
        .where(DailyMetric.readiness_narrative.is_not(None))
        .order_by(DailyMetric.metric_date.desc())
        .limit(1)
    )
    metric_result = await session.execute(metric_stmt)
    metric = metric_result.scalar_one_or_none()
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

    insight: VertexInsight | None = metric.vertex_insight
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
    )
