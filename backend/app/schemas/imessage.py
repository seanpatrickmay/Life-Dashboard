from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IMessageStatusResponse(BaseModel):
    synced_conversations: int
    synced_messages: int
    unprocessed_messages: int
    last_message_at_utc: datetime | None = None
    last_sync_completed_at_utc: datetime | None = None
    last_processing_completed_at_utc: datetime | None = None


class IMessageParticipantResponse(BaseModel):
    identifier: str
    display_name: str | None = None
    is_self: bool = False

    class Config:
        from_attributes = True


class IMessageConversationSummary(BaseModel):
    id: int
    source_guid: str
    display_name: str
    chat_identifier: str | None = None
    service_name: str | None = None
    participants: list[str] = Field(default_factory=list)
    last_message_at_utc: datetime | None = None
    last_synced_at_utc: datetime | None = None
    message_count: int


class IMessageMessageResponse(BaseModel):
    id: int
    conversation_id: int | None = None
    source_guid: str
    is_from_me: bool
    handle_identifier: str | None = None
    sender_label: str | None = None
    text: str | None = None
    normalized_text: str | None = None
    sent_at_utc: datetime | None = None
    has_attachments: bool
    processed_at_utc: datetime | None = None


class IMessageConversationDetailResponse(BaseModel):
    conversation: IMessageConversationSummary
    messages: list[IMessageMessageResponse] = Field(default_factory=list)


class IMessageActionAuditResponse(BaseModel):
    id: int
    action_type: str
    action_fingerprint: str
    status: str
    project_id: int | None = None
    target_page_id: int | None = None
    target_todo_id: int | None = None
    target_calendar_event_id: int | None = None
    target_journal_entry_id: int | None = None
    conversation_id: int | None = None
    supporting_message_ids: list[int] = Field(default_factory=list)
    extracted_payload: dict[str, Any] | None = None
    applied_payload: dict[str, Any] | None = None
    rationale: str | None = None
    judge_reasoning: str | None = None
    applied_at_utc: datetime | None = None
    created_at: datetime


class IMessageSyncRunResponse(BaseModel):
    id: int
    status: str
    started_at_utc: datetime
    completed_at_utc: datetime | None = None
    source_path: str | None = None
    conversations_scanned: int
    conversations_upserted: int
    messages_scanned: int
    messages_upserted: int
    error_message: str | None = None

    class Config:
        from_attributes = True


class IMessageProcessingRunResponse(BaseModel):
    id: int
    status: str
    started_at_utc: datetime
    completed_at_utc: datetime | None = None
    messages_considered: int
    clusters_processed: int
    actions_applied: int
    error_message: str | None = None

    class Config:
        from_attributes = True


class IMessageProcessingTriggerResponse(BaseModel):
    started_at: datetime
    status: str
    run_id: int | None = None
    message: str
