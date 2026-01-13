from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.db.models.entities import User
from app.schemas.system import RefreshStatusResponse
from app.workers.tasks import get_visit_refresh_controller

router = APIRouter(prefix="/system", tags=["system"])


@router.post("/refresh-today", response_model=RefreshStatusResponse)
async def refresh_today_metrics(current_user: User = Depends(get_current_user)) -> RefreshStatusResponse:
    controller = get_visit_refresh_controller()
    status = await controller.request_refresh(user_id=current_user.id)
    return RefreshStatusResponse(**status.__dict__)
