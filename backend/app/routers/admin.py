from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.schemas.admin import IngestionTriggerResponse
from app.services.insight_service import InsightService
from app.services.metrics_service import MetricsService
from app.utils.timezone import eastern_now

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/ingest", response_model=IngestionTriggerResponse)
async def trigger_ingestion(
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
    session: AsyncSession = Depends(get_session),
) -> IngestionTriggerResponse:
    if x_admin_token != settings.readiness_admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")

    metrics = MetricsService(session)
    insight = InsightService(session)
    await metrics.ingest(user_id=1)
    await insight.refresh_daily_insight(user_id=1)

    return IngestionTriggerResponse(
        started_at=eastern_now(),
        status="queued",
        message="Ingestion and insight refresh completed",
    )
