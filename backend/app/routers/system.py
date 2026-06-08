from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.entities import User
from app.db.session import get_session
from app.schemas.system import RefreshStatusResponse
from app.workers.tasks import get_visit_refresh_controller

router = APIRouter(prefix="/system", tags=["system"])


@router.post("/refresh-today", response_model=RefreshStatusResponse)
async def refresh_today_metrics(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RefreshStatusResponse:
    controller = get_visit_refresh_controller()
    status = await controller.request_refresh(session, user_id=current_user.id)
    return RefreshStatusResponse(**status.__dict__)
