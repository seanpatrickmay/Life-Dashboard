"""Read/admin helpers for synced iMessage data."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.imessage import (
    IMessageActionAudit,
    IMessageConversation,
    IMessageMessage,
    IMessageProcessingRun,
    IMessageSyncRun,
)
from app.schemas.imessage import (
    IMessageActionAuditResponse,
    IMessageConversationDetailResponse,
    IMessageConversationSummary,
    IMessageMessageResponse,
    IMessageProcessingRunResponse,
    IMessageStatusResponse,
    IMessageSyncRunResponse,
)
from app.services.imessage_utils import conversation_display_name


class IMessageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_status(self, user_id: int) -> IMessageStatusResponse:
        synced_conversations = await self._count(IMessageConversation, user_id)
        synced_messages = await self._count(IMessageMessage, user_id)
        last_message_at = await self._scalar(
            select(func.max(IMessageConversation.last_message_at_utc)).where(
                IMessageConversation.user_id == user_id
            )
        )
        last_sync = await self._latest_run(IMessageSyncRun, user_id)
        last_processing = await self._latest_run(IMessageProcessingRun, user_id)
        unprocessed_messages = await self._scalar(
            select(func.count(IMessageMessage.id)).where(
                IMessageMessage.user_id == user_id,
                IMessageMessage.processed_at_utc.is_(None),
            )
        )
        return IMessageStatusResponse(
            synced_conversations=synced_conversations,
            synced_messages=synced_messages,
            unprocessed_messages=int(unprocessed_messages or 0),
            last_message_at_utc=last_message_at,
            last_sync_completed_at_utc=last_sync.completed_at_utc if last_sync else None,
            last_processing_completed_at_utc=(
                last_processing.completed_at_utc if last_processing else None
            ),
        )

    async def list_conversations(
        self, user_id: int, *, limit: int = 50, offset: int = 0
    ) -> list[IMessageConversationSummary]:
        message_count = (
            select(
                IMessageMessage.conversation_id.label("conversation_id"),
                func.count(IMessageMessage.id).label("message_count"),
            )
            .where(IMessageMessage.user_id == user_id)
            .group_by(IMessageMessage.conversation_id)
            .subquery()
        )
        stmt = (
            select(IMessageConversation, message_count.c.message_count)
            .outerjoin(message_count, message_count.c.conversation_id == IMessageConversation.id)
            .options(selectinload(IMessageConversation.participants))
            .where(IMessageConversation.user_id == user_id)
            .order_by(IMessageConversation.last_message_at_utc.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            self._conversation_summary(conversation, int(message_count or 0))
            for conversation, message_count in rows
        ]

    async def get_conversation_detail(
        self, user_id: int, conversation_id: int, *, limit: int = 200
    ) -> IMessageConversationDetailResponse | None:
        stmt = (
            select(IMessageConversation)
            .options(selectinload(IMessageConversation.participants))
            .where(
                IMessageConversation.user_id == user_id,
                IMessageConversation.id == conversation_id,
            )
        )
        result = await self.session.execute(stmt)
        conversation = result.scalar_one_or_none()
        if conversation is None:
            return None
        messages_stmt = (
            select(IMessageMessage)
            .where(
                IMessageMessage.user_id == user_id,
                IMessageMessage.conversation_id == conversation_id,
            )
            .order_by(IMessageMessage.sent_at_utc.desc().nullslast(), IMessageMessage.id.desc())
            .limit(limit)
        )
        messages_result = await self.session.execute(messages_stmt)
        messages = list(reversed(messages_result.scalars().all()))
        return IMessageConversationDetailResponse(
            conversation=self._conversation_summary(conversation, len(messages)),
            messages=[self._message_response(item) for item in messages],
        )

    async def list_action_audits(
        self, user_id: int, *, limit: int = 100, offset: int = 0
    ) -> list[IMessageActionAuditResponse]:
        stmt = (
            select(IMessageActionAudit)
            .where(IMessageActionAudit.user_id == user_id)
            .order_by(IMessageActionAudit.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._action_audit_response(item) for item in result.scalars().all()]

    async def list_sync_runs(
        self, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[IMessageSyncRunResponse]:
        stmt = (
            select(IMessageSyncRun)
            .where(IMessageSyncRun.user_id == user_id)
            .order_by(IMessageSyncRun.started_at_utc.desc(), IMessageSyncRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [IMessageSyncRunResponse.model_validate(item) for item in result.scalars().all()]

    async def list_processing_runs(
        self, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[IMessageProcessingRunResponse]:
        stmt = (
            select(IMessageProcessingRun)
            .where(IMessageProcessingRun.user_id == user_id)
            .order_by(IMessageProcessingRun.started_at_utc.desc(), IMessageProcessingRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            IMessageProcessingRunResponse.model_validate(item) for item in result.scalars().all()
        ]

    async def _count(self, model: type, user_id: int) -> int:
        value = await self._scalar(select(func.count(model.id)).where(model.user_id == user_id))
        return int(value or 0)

    async def _scalar(self, stmt) -> int | datetime | None:
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _latest_run(self, model: type, user_id: int):
        stmt = (
            select(model)
            .where(model.user_id == user_id)
            .order_by(model.started_at_utc.desc(), model.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _conversation_summary(
        self, conversation: IMessageConversation, message_count: int
    ) -> IMessageConversationSummary:
        participants = [item.display_name or item.identifier for item in conversation.participants]
        return IMessageConversationSummary(
            id=conversation.id,
            source_guid=conversation.source_guid,
            display_name=conversation_display_name(
                display_name=conversation.display_name,
                chat_identifier=conversation.chat_identifier,
                participants=participants,
            ),
            chat_identifier=conversation.chat_identifier,
            service_name=conversation.service_name,
            participants=participants,
            last_message_at_utc=conversation.last_message_at_utc,
            last_synced_at_utc=conversation.last_synced_at_utc,
            message_count=message_count,
        )

    def _message_response(self, message: IMessageMessage) -> IMessageMessageResponse:
        return IMessageMessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            source_guid=message.source_guid,
            is_from_me=message.is_from_me,
            handle_identifier=message.handle_identifier,
            sender_label=message.sender_label,
            text=message.text,
            normalized_text=message.normalized_text,
            sent_at_utc=message.sent_at_utc,
            has_attachments=message.has_attachments,
            processed_at_utc=message.processed_at_utc,
        )

    def _action_audit_response(self, audit: IMessageActionAudit) -> IMessageActionAuditResponse:
        return IMessageActionAuditResponse(
            id=audit.id,
            action_type=audit.action_type,
            action_fingerprint=audit.action_fingerprint,
            status=audit.status,
            project_id=audit.project_id,
            target_page_id=audit.target_page_id,
            target_todo_id=audit.target_todo_id,
            target_calendar_event_id=audit.target_calendar_event_id,
            target_journal_entry_id=audit.target_journal_entry_id,
            conversation_id=audit.conversation_id,
            supporting_message_ids=[int(item) for item in (audit.supporting_message_ids_json or [])],
            extracted_payload=audit.extracted_payload,
            applied_payload=audit.applied_payload,
            rationale=audit.rationale,
            judge_reasoning=audit.judge_reasoning,
            applied_at_utc=audit.applied_at_utc,
            created_at=audit.created_at,
        )
