from __future__ import annotations

from fastapi import APIRouter

from app.schemas.system import RefreshStatusResponse
from app.workers.tasks import get_visit_refresh_controller

router = APIRouter(prefix="/system", tags=["system"])
DEFAULT_USER_ID = 1


@router.post("/refresh-today", response_model=RefreshStatusResponse)
async def refresh_today_metrics() -> RefreshStatusResponse:
    controller = get_visit_refresh_controller()
    status = await controller.request_refresh(user_id=DEFAULT_USER_ID)
    return RefreshStatusResponse(**status.__dict__)
