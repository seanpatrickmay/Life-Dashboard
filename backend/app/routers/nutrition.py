from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import NutritionFoodStatus
from app.db.repositories.nutrition_goals_repository import NutritionGoalsRepository
from app.db.session import get_session
from app.schemas.nutrition import (
    ClaudeMessageRequest,
    ClaudeMessageResponse,
    LogIntakeRequest,
    NutritionIntakeUpdateRequest,
    NutrientDefinitionResponse,
    NutritionIntakeEntry,
    NutritionIntakeMenuResponse,
    NutritionDailySummaryResponse,
    NutritionFoodPayload,
    NutritionFoodResponse,
    NutritionHistoryResponse,
    NutrientGoalItem,
    NutrientGoalUpdateRequest,
    ScalingRuleListResponse,
)
from app.services.claude_nutrition_agent import ClaudeNutritionAgent
from app.services.nutrition_foods_service import NutritionFoodsService
from app.services.nutrition_goals_service import NutritionGoalsService
from app.services.nutrition_intake_service import NutritionIntakeService
from app.utils.timezone import eastern_today


router = APIRouter(prefix="/nutrition", tags=["nutrition"])
DEFAULT_USER_ID = 1


@router.get("/nutrients", response_model=list[NutrientDefinitionResponse])
async def list_nutrients(
    session: AsyncSession = Depends(get_session),
) -> list[NutrientDefinitionResponse]:
    repo = NutritionGoalsRepository(session)
    nutrients = await repo.list_nutrients()
    return [
        NutrientDefinitionResponse(
            slug=nutrient.slug,
            display_name=nutrient.display_name,
            category=nutrient.category.value,
            group=nutrient.group.value,
            unit=nutrient.unit,
            default_goal=nutrient.default_goal,
        )
        for nutrient in nutrients
    ]


@router.get("/foods", response_model=list[NutritionFoodResponse])
async def get_foods(
    session: AsyncSession = Depends(get_session),
) -> list[NutritionFoodResponse]:
    service = NutritionFoodsService(session)
    foods = await service.list_foods()
    return [NutritionFoodResponse(**food) for food in foods]


@router.post("/foods", response_model=NutritionFoodResponse)
async def create_food(
    payload: NutritionFoodPayload, session: AsyncSession = Depends(get_session)
) -> NutritionFoodResponse:
    service = NutritionFoodsService(session)
    status = (
        NutritionFoodStatus(payload.status.lower())
        if payload.status
        else NutritionFoodStatus.UNCONFIRMED
    )
    record = await service.create_food(
        name=payload.name,
        default_unit=payload.default_unit,
        source=payload.source,
        status=status,
        nutrient_values=payload.nutrients,
    )
    return NutritionFoodResponse(**record)


@router.patch("/foods/{food_id}", response_model=NutritionFoodResponse)
async def update_food(
    food_id: int,
    payload: NutritionFoodPayload,
    session: AsyncSession = Depends(get_session),
) -> NutritionFoodResponse:
    service = NutritionFoodsService(session)
    status = (
        NutritionFoodStatus(payload.status.lower()) if payload.status else None
    )
    try:
        record = await service.update_food(
            food_id,
            name=payload.name,
            default_unit=payload.default_unit,
            status=status,
            nutrient_values=payload.nutrients,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NutritionFoodResponse(**record)


@router.get("/goals", response_model=list[NutrientGoalItem])
async def list_goals(
    session: AsyncSession = Depends(get_session),
) -> list[NutrientGoalItem]:
    service = NutritionGoalsService(session)
    goals = await service.list_goals(DEFAULT_USER_ID)
    return [NutrientGoalItem(**goal) for goal in goals]


@router.put("/goals/{slug}", response_model=NutrientGoalItem)
async def update_goal(
    slug: str,
    body: NutrientGoalUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> NutrientGoalItem:
    service = NutritionGoalsService(session)
    try:
        result = await service.update_goal(DEFAULT_USER_ID, slug, body.goal)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return NutrientGoalItem(**result)


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


@router.post("/intake/manual", response_model=dict)
async def log_manual_intake(
    request: LogIntakeRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    service = NutritionIntakeService(session)
    day = request.day or eastern_today()
    try:
        record = await service.log_manual_intake(
            user_id=DEFAULT_USER_ID,
            food_id=request.food_id,
            quantity=request.quantity,
            unit=request.unit,
            day=day,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return record

@router.get("/intake/menu", response_model=NutritionIntakeMenuResponse)
async def list_today_menu(
    day: date | None = None, session: AsyncSession = Depends(get_session)
) -> NutritionIntakeMenuResponse:
    service = NutritionIntakeService(session)
    day_value = day or eastern_today()
    items = await service.list_day_menu(DEFAULT_USER_ID, day_value)
    return NutritionIntakeMenuResponse(day=day_value, entries=items)


@router.patch("/intake/{intake_id}", response_model=NutritionIntakeEntry)
async def update_intake_entry(
    intake_id: int,
    payload: NutritionIntakeUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> NutritionIntakeEntry:
    service = NutritionIntakeService(session)
    try:
        updated = await service.update_intake(
            intake_id,
            quantity=payload.quantity,
            unit=payload.unit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NutritionIntakeEntry(**updated)


@router.delete("/intake/{intake_id}", status_code=204, response_class=Response)
async def delete_intake_entry(
    intake_id: int, session: AsyncSession = Depends(get_session)
) -> Response:
    service = NutritionIntakeService(session)
    await service.delete_intake(intake_id)
    return Response(status_code=204)


@router.get("/intake/daily", response_model=NutritionDailySummaryResponse)
async def daily_summary(
    day: date | None = None, session: AsyncSession = Depends(get_session)
) -> NutritionDailySummaryResponse:
    service = NutritionIntakeService(session)
    summary = await service.daily_summary(DEFAULT_USER_ID, day or eastern_today())
    return NutritionDailySummaryResponse(**summary)


@router.get("/intake/history", response_model=NutritionHistoryResponse)
async def history(
    days: int = 14, session: AsyncSession = Depends(get_session)
) -> NutritionHistoryResponse:
    service = NutritionIntakeService(session)
    data = await service.rolling_average(DEFAULT_USER_ID, days)
    return NutritionHistoryResponse(**data)


@router.post("/claude/message", response_model=ClaudeMessageResponse)
async def claude_message(
    payload: ClaudeMessageRequest, session: AsyncSession = Depends(get_session)
) -> ClaudeMessageResponse:
    agent = ClaudeNutritionAgent(session)
    session_id = payload.session_id or str(uuid4())
    response = await agent.respond(DEFAULT_USER_ID, payload.message, session_id)
    return ClaudeMessageResponse(
        session_id=session_id,
        reply=response.reply,
        logged_entries=response.logged_entries,
    )
