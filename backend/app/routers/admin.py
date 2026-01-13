from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.db.session import get_session
from app.db.models.entities import User
from app.schemas.admin import IngestionTriggerResponse
from app.services.insight_service import InsightService
from app.services.metrics_service import MetricsService
from app.utils.timezone import eastern_now

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/ingest", response_model=IngestionTriggerResponse)
async def trigger_ingestion(
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> IngestionTriggerResponse:
    metrics = MetricsService(session)
    insight = InsightService(session)
    await metrics.ingest(user_id=current_user.id)
    await insight.refresh_daily_insight(user_id=current_user.id)

    return IngestionTriggerResponse(
        started_at=eastern_now(),
        status="queued",
        message="Ingestion and insight refresh completed",
    )
