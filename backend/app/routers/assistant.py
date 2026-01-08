from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.assistant import MonetMessageRequest, MonetMessageResponse
from app.services.monet_assistant import MonetAssistantAgent

router = APIRouter(prefix="/assistant", tags=["assistant"])

DEFAULT_USER_ID = 1


@router.post("/monet-message", response_model=MonetMessageResponse)
async def monet_message(
    payload: MonetMessageRequest,
    session: AsyncSession = Depends(get_session),
) -> MonetMessageResponse:
    agent = MonetAssistantAgent(session)
    result = await agent.respond(
        DEFAULT_USER_ID,
        message=payload.message,
        session_id=payload.session_id,
        window_days=payload.window_days,
        time_zone=payload.time_zone,
    )
    return MonetMessageResponse(
        session_id=result.session_id,
        reply=result.reply,
        nutrition_entries=result.nutrition_entries,
        todo_items=result.todo_items,
        tools_used=result.tools_used,
    )
