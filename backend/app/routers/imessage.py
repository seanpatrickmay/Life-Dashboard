from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.entities import User
from app.db.session import get_session
from app.schemas.imessage import (
    IMessageActionAuditResponse,
    IMessageConversationDetailResponse,
    IMessageConversationSummary,
    IMessageProcessingRunResponse,
    IMessageProcessingTriggerResponse,
    IMessageStatusResponse,
    IMessageSyncRunResponse,
)
from app.services.imessage_processing_service import IMessageProcessingService
from app.services.imessage_service import IMessageService

router = APIRouter(prefix="/imessage", tags=["imessage"])


@router.get("/status", response_model=IMessageStatusResponse)
async def get_imessage_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IMessageStatusResponse:
    service = IMessageService(session)
    return await service.get_status(current_user.id)


@router.get("/conversations", response_model=list[IMessageConversationSummary])
async def list_imessage_conversations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[IMessageConversationSummary]:
    service = IMessageService(session)
    return await service.list_conversations(current_user.id, limit=limit, offset=offset)


@router.get("/conversations/{conversation_id}", response_model=IMessageConversationDetailResponse | None)
async def get_imessage_conversation_detail(
    conversation_id: int,
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IMessageConversationDetailResponse | None:
    service = IMessageService(session)
    return await service.get_conversation_detail(current_user.id, conversation_id, limit=limit)


@router.get("/actions", response_model=list[IMessageActionAuditResponse])
async def list_imessage_action_audits(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[IMessageActionAuditResponse]:
    service = IMessageService(session)
    return await service.list_action_audits(current_user.id, limit=limit, offset=offset)


@router.get("/sync-runs", response_model=list[IMessageSyncRunResponse])
async def list_imessage_sync_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[IMessageSyncRunResponse]:
    service = IMessageService(session)
    return await service.list_sync_runs(current_user.id, limit=limit, offset=offset)


@router.get("/processing-runs", response_model=list[IMessageProcessingRunResponse])
async def list_imessage_processing_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[IMessageProcessingRunResponse]:
    service = IMessageService(session)
    return await service.list_processing_runs(current_user.id, limit=limit, offset=offset)


@router.post("/process", response_model=IMessageProcessingTriggerResponse)
async def process_imessage_now(
    time_zone: str = Query("America/New_York"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IMessageProcessingTriggerResponse:
    service = IMessageProcessingService(session)
    run = await service.process_pending_messages(user_id=current_user.id, time_zone=time_zone)
    return IMessageProcessingTriggerResponse(
        started_at=run.started_at_utc if run.started_at_utc else datetime.now(timezone.utc),
        status=run.status,
        run_id=run.id,
        message=run.error_message or "Processing completed.",
    )
