"""Add iMessage sync + processing tables.

Revision ID: 20260317_imessage_pipeline
Revises: 20260316_workspace_v2
Create Date: 2026-03-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_imessage_pipeline"
down_revision = "20260316_workspace_v2"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "imessage_conversation" not in table_names:
        op.create_table(
            "imessage_conversation",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source_guid", sa.String(length=255), nullable=False),
            sa.Column("source_row_id", sa.BigInteger(), nullable=True),
            sa.Column("service_name", sa.String(length=64), nullable=True),
            sa.Column("chat_identifier", sa.String(length=255), nullable=True),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("participant_hash", sa.String(length=64), nullable=True),
            sa.Column("participants_json", sa.JSON(), nullable=True),
            sa.Column("last_message_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_synced_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "source_guid", name="uq_imessage_conversation_user_source_guid"),
        )
        op.create_index("ix_imessage_conversation_user_id", "imessage_conversation", ["user_id"], unique=False)
        op.create_index("ix_imessage_conversation_source_row_id", "imessage_conversation", ["source_row_id"], unique=False)
        op.create_index(
            "ix_imessage_conversation_last_message_at_utc",
            "imessage_conversation",
            ["last_message_at_utc"],
            unique=False,
        )

    if "imessage_participant" not in table_names:
        op.create_table(
            "imessage_participant",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("identifier", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("is_self", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.ForeignKeyConstraint(["conversation_id"], ["imessage_conversation.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "conversation_id",
                "identifier",
                name="uq_imessage_participant_conversation_identifier",
            ),
        )
        op.create_index("ix_imessage_participant_user_id", "imessage_participant", ["user_id"], unique=False)
        op.create_index(
            "ix_imessage_participant_conversation_id", "imessage_participant", ["conversation_id"], unique=False
        )

    if "imessage_message" not in table_names:
        op.create_table(
            "imessage_message",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("source_guid", sa.String(length=255), nullable=False),
            sa.Column("source_row_id", sa.BigInteger(), nullable=True),
            sa.Column("service_name", sa.String(length=64), nullable=True),
            sa.Column("handle_identifier", sa.String(length=255), nullable=True),
            sa.Column("sender_label", sa.String(length=255), nullable=True),
            sa.Column("is_from_me", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("normalized_text", sa.Text(), nullable=True),
            sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sent_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("delivered_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("read_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("processed_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("raw_payload", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["conversation_id"], ["imessage_conversation.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "source_guid", name="uq_imessage_message_user_source_guid"),
        )
        op.create_index("ix_imessage_message_user_id", "imessage_message", ["user_id"], unique=False)
        op.create_index("ix_imessage_message_conversation_id", "imessage_message", ["conversation_id"], unique=False)
        op.create_index("ix_imessage_message_source_row_id", "imessage_message", ["source_row_id"], unique=False)
        op.create_index("ix_imessage_message_sent_at_utc", "imessage_message", ["sent_at_utc"], unique=False)
        op.create_index(
            "ix_imessage_message_processed_at_utc", "imessage_message", ["processed_at_utc"], unique=False
        )

    if "imessage_sync_run" not in table_names:
        op.create_table(
            "imessage_sync_run",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_path", sa.String(length=512), nullable=True),
            sa.Column("conversations_scanned", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("conversations_upserted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("messages_scanned", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("messages_upserted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_imessage_sync_run_user_id", "imessage_sync_run", ["user_id"], unique=False)

    if "imessage_processing_run" not in table_names:
        op.create_table(
            "imessage_processing_run",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("messages_considered", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("clusters_processed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("actions_applied", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_imessage_processing_run_user_id", "imessage_processing_run", ["user_id"], unique=False
        )

    if "imessage_action_audit" not in table_names:
        op.create_table(
            "imessage_action_audit",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("processing_run_id", sa.Integer(), nullable=True),
            sa.Column("conversation_id", sa.Integer(), nullable=True),
            sa.Column("action_type", sa.String(length=64), nullable=False),
            sa.Column("action_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("target_page_id", sa.Integer(), nullable=True),
            sa.Column("target_todo_id", sa.Integer(), nullable=True),
            sa.Column("target_calendar_event_id", sa.Integer(), nullable=True),
            sa.Column("target_journal_entry_id", sa.Integer(), nullable=True),
            sa.Column("supporting_message_ids_json", sa.JSON(), nullable=True),
            sa.Column("extracted_payload", sa.JSON(), nullable=True),
            sa.Column("applied_payload", sa.JSON(), nullable=True),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("judge_reasoning", sa.Text(), nullable=True),
            sa.Column("applied_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["conversation_id"], ["imessage_conversation.id"]),
            sa.ForeignKeyConstraint(["processing_run_id"], ["imessage_processing_run.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.ForeignKeyConstraint(["target_calendar_event_id"], ["calendar_event.id"]),
            sa.ForeignKeyConstraint(["target_journal_entry_id"], ["journal_entry.id"]),
            sa.ForeignKeyConstraint(["target_page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["target_todo_id"], ["todo_item.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_imessage_action_audit_user_id", "imessage_action_audit", ["user_id"], unique=False)
        op.create_index(
            "ix_imessage_action_audit_processing_run_id",
            "imessage_action_audit",
            ["processing_run_id"],
            unique=False,
        )
        op.create_index(
            "ix_imessage_action_audit_conversation_id",
            "imessage_action_audit",
            ["conversation_id"],
            unique=False,
        )
        op.create_index(
            "ix_imessage_action_audit_action_type", "imessage_action_audit", ["action_type"], unique=False
        )
        op.create_index(
            "ix_imessage_action_audit_action_fingerprint",
            "imessage_action_audit",
            ["action_fingerprint"],
            unique=False,
        )
        op.create_index("ix_imessage_action_audit_status", "imessage_action_audit", ["status"], unique=False)
        op.create_index("ix_imessage_action_audit_project_id", "imessage_action_audit", ["project_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    for index_name in (
        "ix_imessage_action_audit_project_id",
        "ix_imessage_action_audit_status",
        "ix_imessage_action_audit_action_fingerprint",
        "ix_imessage_action_audit_action_type",
        "ix_imessage_action_audit_conversation_id",
        "ix_imessage_action_audit_processing_run_id",
        "ix_imessage_action_audit_user_id",
    ):
        if "imessage_action_audit" in table_names:
            op.drop_index(index_name, table_name="imessage_action_audit")
    if "imessage_action_audit" in table_names:
        op.drop_table("imessage_action_audit")

    if "imessage_processing_run" in table_names:
        op.drop_index("ix_imessage_processing_run_user_id", table_name="imessage_processing_run")
        op.drop_table("imessage_processing_run")

    if "imessage_sync_run" in table_names:
        op.drop_index("ix_imessage_sync_run_user_id", table_name="imessage_sync_run")
        op.drop_table("imessage_sync_run")

    if "imessage_message" in table_names:
        op.drop_index("ix_imessage_message_processed_at_utc", table_name="imessage_message")
        op.drop_index("ix_imessage_message_sent_at_utc", table_name="imessage_message")
        op.drop_index("ix_imessage_message_source_row_id", table_name="imessage_message")
        op.drop_index("ix_imessage_message_conversation_id", table_name="imessage_message")
        op.drop_index("ix_imessage_message_user_id", table_name="imessage_message")
        op.drop_table("imessage_message")

    if "imessage_participant" in table_names:
        op.drop_index("ix_imessage_participant_conversation_id", table_name="imessage_participant")
        op.drop_index("ix_imessage_participant_user_id", table_name="imessage_participant")
        op.drop_table("imessage_participant")

    if "imessage_conversation" in table_names:
        op.drop_index(
            "ix_imessage_conversation_last_message_at_utc", table_name="imessage_conversation"
        )
        op.drop_index("ix_imessage_conversation_source_row_id", table_name="imessage_conversation")
        op.drop_index("ix_imessage_conversation_user_id", table_name="imessage_conversation")
        op.drop_table("imessage_conversation")
