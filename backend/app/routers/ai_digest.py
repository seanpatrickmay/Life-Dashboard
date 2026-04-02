"""AI Digest API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.entities import User
from app.db.session import get_session
from app.schemas.ai_digest import DigestItemResponse, DigestResponse, RefreshResponse
from app.services.ai_digest_service import AIDigestService
from app.workers.tasks import get_digest_refresh_controller

router = APIRouter(prefix="/ai-digest", tags=["ai-digest"])


@router.get("/today", response_model=DigestResponse)
async def get_today_digest(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DigestResponse:
    service = AIDigestService(session)
    is_stale = await service.is_stale()

    if is_stale:
        controller = get_digest_refresh_controller()
        await controller.request_refresh()

    items = await service.get_today_items()
    last_refreshed = await service.get_latest_refresh_time()

    return DigestResponse(
        items=[DigestItemResponse.model_validate(item) for item in items],
        last_refreshed=last_refreshed,
        item_count=len(items),
        is_stale=is_stale,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_digest(
    current_user: User = Depends(get_current_user),
) -> RefreshResponse:
    controller = get_digest_refresh_controller()
    status = await controller.request_refresh(force=True)
    return RefreshResponse(started=status.job_started, message=status.message or "")
