"""Raw iMessage sync + processing audit models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class IMessageConversation(Base):
    __tablename__ = "imessage_conversation"
    __table_args__ = (
        UniqueConstraint("user_id", "source_guid", name="uq_imessage_conversation_user_source_guid"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    source_guid: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    service_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chat_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    participant_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    participants_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    last_message_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_synced_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="imessage_conversations")
    participants: Mapped[list["IMessageParticipant"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="IMessageParticipant.id.asc()",
    )
    messages: Mapped[list["IMessageMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="IMessageMessage.sent_at_utc.asc().nullslast(), IMessageMessage.id.asc()",
    )
    action_audits: Mapped[list["IMessageActionAudit"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class IMessageParticipant(Base):
    __tablename__ = "imessage_participant"
    __table_args__ = (
        UniqueConstraint("conversation_id", "identifier", name="uq_imessage_participant_conversation_identifier"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("imessage_conversation.id"), nullable=False, index=True
    )
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_self: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    conversation: Mapped[IMessageConversation] = relationship(back_populates="participants")


class IMessageContactIdentity(Base):
    __tablename__ = "imessage_contact_identity"
    __table_args__ = (
        UniqueConstraint("user_id", "identifier", name="uq_imessage_contact_identity_user_identifier"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    identifier_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolved_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_resolved_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="imessage_contact_identities")


class IMessageMessage(Base):
    __tablename__ = "imessage_message"
    __table_args__ = (
        UniqueConstraint("user_id", "source_guid", name="uq_imessage_message_user_source_guid"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("imessage_conversation.id"), nullable=False, index=True
    )
    source_guid: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    service_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    handle_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_from_me: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="imessage_messages")
    conversation: Mapped[IMessageConversation] = relationship(back_populates="messages")


class IMessageSyncRun(Base):
    __tablename__ = "imessage_sync_run"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    conversations_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversations_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="imessage_sync_runs")


class IMessageProcessingRun(Base):
    __tablename__ = "imessage_processing_run"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    messages_considered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clusters_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actions_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_fallback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="imessage_processing_runs")
    action_audits: Mapped[list["IMessageActionAudit"]] = relationship(
        back_populates="processing_run",
        cascade="all, delete-orphan",
    )


class IMessageActionAudit(Base):
    __tablename__ = "imessage_action_audit"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    processing_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("imessage_processing_run.id"), nullable=True, index=True
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("imessage_conversation.id"), nullable=True, index=True
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("project.id"), nullable=True, index=True)
    target_page_id: Mapped[int | None] = mapped_column(ForeignKey("workspace_page.id"), nullable=True)
    target_todo_id: Mapped[int | None] = mapped_column(
        ForeignKey("todo_item.id", ondelete="SET NULL"), nullable=True
    )
    target_calendar_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("calendar_event.id"), nullable=True
    )
    target_journal_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entry.id"), nullable=True
    )
    extraction_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    supporting_message_ids_json: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    extracted_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applied_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_occurred_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="imessage_action_audits")
    conversation: Mapped[IMessageConversation | None] = relationship(back_populates="action_audits")
    processing_run: Mapped[IMessageProcessingRun | None] = relationship(back_populates="action_audits")
