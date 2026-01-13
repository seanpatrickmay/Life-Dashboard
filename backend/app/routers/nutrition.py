from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.quotas import enforce_chat_quota
from app.db.models.nutrition import NUTRIENT_DEFINITIONS, NutritionIngredientStatus
from app.db.models.entities import User
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
    NutritionIngredientPayload,
    NutritionIngredientResponse,
    NutritionRecipePayload,
    NutritionRecipeResponse,
    RecipeSuggestion,
    NutritionHistoryResponse,
    NutrientGoalItem,
    NutrientGoalUpdateRequest,
    ScalingRuleListResponse,
)
from app.services.claude_nutrition_agent import ClaudeNutritionAgent
from app.services.nutrition_ingredients_service import NutritionIngredientsService
from app.services.nutrition_recipes_service import NutritionRecipesService
from app.services.nutrition_goals_service import NutritionGoalsService
from app.services.nutrition_intake_service import NutritionIntakeService
from app.utils.timezone import eastern_today


router = APIRouter(prefix="/nutrition", tags=["nutrition"])


@router.get("/nutrients", response_model=list[NutrientDefinitionResponse])
async def list_nutrients(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NutrientDefinitionResponse]:
    repo = NutritionGoalsRepository(session)
    nutrients = await repo.list_nutrients()
    if not nutrients:
        nutrients = list(NUTRIENT_DEFINITIONS)
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


@router.get("/ingredients", response_model=list[NutritionIngredientResponse])
async def get_ingredients(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NutritionIngredientResponse]:
    service = NutritionIngredientsService(session)
    ingredients = await service.list_ingredients(current_user.id)
    return [NutritionIngredientResponse(**item) for item in ingredients]


@router.post("/ingredients", response_model=NutritionIngredientResponse)
async def create_ingredient(
    payload: NutritionIngredientPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionIngredientResponse:
    service = NutritionIngredientsService(session)
    status = (
        NutritionIngredientStatus(payload.status.lower())
        if payload.status
        else NutritionIngredientStatus.UNCONFIRMED
    )
    record = await service.create_ingredient(
        name=payload.name,
        default_unit=payload.default_unit,
        source=payload.source,
        status=status,
        nutrient_values=payload.nutrients,
        owner_user_id=current_user.id,
    )
    return NutritionIngredientResponse(**record)


@router.patch("/ingredients/{ingredient_id}", response_model=NutritionIngredientResponse)
async def update_ingredient(
    ingredient_id: int,
    payload: NutritionIngredientPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionIngredientResponse:
    service = NutritionIngredientsService(session)
    status = (
        NutritionIngredientStatus(payload.status.lower()) if payload.status else None
    )
    try:
        record = await service.update_ingredient(
            ingredient_id,
            owner_user_id=current_user.id,
            name=payload.name,
            default_unit=payload.default_unit,
            status=status,
            nutrient_values=payload.nutrients,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NutritionIngredientResponse(**record)


@router.get("/recipes", response_model=list[NutritionRecipeResponse])
async def list_recipes(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NutritionRecipeResponse]:
    service = NutritionRecipesService(session)
    recipes = await service.list_recipes(current_user.id)
    return [NutritionRecipeResponse(**recipe) for recipe in recipes]


@router.get("/recipes/{recipe_id}", response_model=NutritionRecipeResponse)
async def get_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionRecipeResponse:
    service = NutritionRecipesService(session)
    try:
        recipe = await service.get_recipe(recipe_id, owner_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NutritionRecipeResponse(**recipe)


@router.post("/recipes", response_model=NutritionRecipeResponse)
async def create_recipe(
    payload: NutritionRecipePayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionRecipeResponse:
    service = NutritionRecipesService(session)
    status = (
        NutritionIngredientStatus(payload.status.lower())
        if payload.status
        else NutritionIngredientStatus.UNCONFIRMED
    )
    record = await service.create_recipe(
        name=payload.name,
        default_unit=payload.default_unit,
        servings=payload.servings,
        status=status,
        owner_user_id=current_user.id,
        components=[
            {
                "ingredient_id": comp.ingredient_id,
                "child_recipe_id": comp.child_recipe_id,
                "quantity": comp.quantity,
                "unit": comp.unit,
                "position": comp.position,
            }
            for comp in payload.components
        ],
    )
    return NutritionRecipeResponse(**record)


@router.patch("/recipes/{recipe_id}", response_model=NutritionRecipeResponse)
async def update_recipe(
    recipe_id: int,
    payload: NutritionRecipePayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionRecipeResponse:
    service = NutritionRecipesService(session)
    status = (
        NutritionIngredientStatus(payload.status.lower()) if payload.status else None
    )
    try:
        record = await service.update_recipe(
            recipe_id,
            owner_user_id=current_user.id,
            name=payload.name,
            default_unit=payload.default_unit,
            servings=payload.servings,
            status=status,
            components=[
                {
                    "ingredient_id": comp.ingredient_id,
                    "child_recipe_id": comp.child_recipe_id,
                    "quantity": comp.quantity,
                    "unit": comp.unit,
                    "position": comp.position,
                }
                for comp in payload.components
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NutritionRecipeResponse(**record)


@router.post("/recipes/suggest", response_model=RecipeSuggestion)
async def suggest_recipe(
    description: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RecipeSuggestion:
    agent = ClaudeNutritionAgent(session)
    suggestion = await agent._suggest_recipe(description)  # re-use agent logic
    if suggestion is None:
        raise HTTPException(status_code=400, detail="Unable to suggest recipe from description")
    return RecipeSuggestion(**suggestion)


@router.get("/goals", response_model=list[NutrientGoalItem])
async def list_goals(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[NutrientGoalItem]:
    service = NutritionGoalsService(session)
    goals = await service.list_goals(current_user.id)
    return [NutrientGoalItem(**goal) for goal in goals]


@router.put("/goals/{slug}", response_model=NutrientGoalItem)
async def update_goal(
    slug: str,
    body: NutrientGoalUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutrientGoalItem:
    service = NutritionGoalsService(session)
    try:
        result = await service.update_goal(current_user.id, slug, body.goal)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return NutrientGoalItem(**result)


@router.get("/scaling-rules", response_model=ScalingRuleListResponse)
async def get_scaling_rules(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ScalingRuleListResponse:
    service = NutritionGoalsService(session)
    data = await service.list_scaling_rules(current_user.id)
    return ScalingRuleListResponse(**data)


@router.post("/scaling-rules/{slug}", status_code=204)
async def enable_scaling_rule(
    slug: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = NutritionGoalsService(session)
    try:
        await service.set_rule_state(current_user.id, slug, True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return Response(status_code=204)


@router.delete("/scaling-rules/{slug}", status_code=204)
async def disable_scaling_rule(
    slug: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = NutritionGoalsService(session)
    try:
        await service.set_rule_state(current_user.id, slug, False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return Response(status_code=204)


@router.post("/intake/manual", response_model=dict)
async def log_manual_intake(
    request: LogIntakeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = NutritionIntakeService(session)
    day = request.day or eastern_today()
    try:
        record = await service.log_manual_intake(
            user_id=current_user.id,
            ingredient_id=request.ingredient_id,
            recipe_id=request.recipe_id,
            quantity=request.quantity,
            unit=request.unit,
            day=day,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return record

@router.get("/intake/menu", response_model=NutritionIntakeMenuResponse)
async def list_today_menu(
    day: date | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionIntakeMenuResponse:
    service = NutritionIntakeService(session)
    day_value = day or eastern_today()
    items = await service.list_day_menu(current_user.id, day_value)
    return NutritionIntakeMenuResponse(day=day_value, entries=items)


@router.patch("/intake/{intake_id}", response_model=NutritionIntakeEntry)
async def update_intake_entry(
    intake_id: int,
    payload: NutritionIntakeUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionIntakeEntry:
    service = NutritionIntakeService(session)
    try:
        updated = await service.update_intake(
            intake_id,
            owner_user_id=current_user.id,
            quantity=payload.quantity,
            unit=payload.unit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NutritionIntakeEntry(**updated)


@router.delete("/intake/{intake_id}", status_code=204, response_class=Response)
async def delete_intake_entry(
    intake_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    service = NutritionIntakeService(session)
    await service.delete_intake(intake_id, owner_user_id=current_user.id)
    return Response(status_code=204)


@router.get("/intake/daily", response_model=NutritionDailySummaryResponse)
async def daily_summary(
    day: date | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionDailySummaryResponse:
    service = NutritionIntakeService(session)
    summary = await service.daily_summary(current_user.id, day or eastern_today())
    return NutritionDailySummaryResponse(**summary)


@router.get("/intake/history", response_model=NutritionHistoryResponse)
async def history(
    days: int = 14,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NutritionHistoryResponse:
    service = NutritionIntakeService(session)
    data = await service.rolling_average(current_user.id, days)
    return NutritionHistoryResponse(**data)


@router.post("/claude/message", response_model=ClaudeMessageResponse)
async def claude_message(
    payload: ClaudeMessageRequest,
    current_user: User = Depends(enforce_chat_quota),
    session: AsyncSession = Depends(get_session),
) -> ClaudeMessageResponse:
    agent = ClaudeNutritionAgent(session)
    session_id = payload.session_id or str(uuid4())
    response = await agent.respond(current_user.id, payload.message, session_id)
    return ClaudeMessageResponse(
        session_id=session_id,
        reply=response.reply,
        logged_entries=response.logged_entries,
    )
