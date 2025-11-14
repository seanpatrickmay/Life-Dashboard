from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.nutrition import ScalingRuleListResponse
from app.schemas.user_profile import (
    UserProfileResponse,
    UserProfileUpdateRequest,
)
from app.services.nutrition_goals_service import NutritionGoalsService
from app.services.user_profile_service import UserProfileService

router = APIRouter(prefix="/user", tags=["user"])
DEFAULT_USER_ID = 1


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    session: AsyncSession = Depends(get_session),
) -> UserProfileResponse:
    service = UserProfileService(session)
    payload = await service.fetch_profile_payload(DEFAULT_USER_ID)
    return UserProfileResponse(**payload)


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    body: UserProfileUpdateRequest, session: AsyncSession = Depends(get_session)
) -> UserProfileResponse:
    service = UserProfileService(session)
    try:
        await service.update_profile(DEFAULT_USER_ID, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    payload = await service.fetch_profile_payload(DEFAULT_USER_ID)
    return UserProfileResponse(**payload)


@router.get("/scaling-rules", response_model=ScalingRuleListResponse)
async def get_scaling_rules(
    session: AsyncSession = Depends(get_session),
) -> ScalingRuleListResponse:
    service = NutritionGoalsService(session)
    data = await service.list_scaling_rules(DEFAULT_USER_ID)
    return ScalingRuleListResponse(**data)


@router.post("/scaling-rules/{slug}", status_code=204)
async def enable_scaling_rule(
    slug: str, session: AsyncSession = Depends(get_session)
) -> Response:
    service = NutritionGoalsService(session)
    try:
        await service.set_rule_state(DEFAULT_USER_ID, slug, True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return Response(status_code=204)


@router.delete("/scaling-rules/{slug}", status_code=204)
async def disable_scaling_rule(
    slug: str, session: AsyncSession = Depends(get_session)
) -> Response:
    service = NutritionGoalsService(session)
    try:
        await service.set_rule_state(DEFAULT_USER_ID, slug, False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return Response(status_code=204)
