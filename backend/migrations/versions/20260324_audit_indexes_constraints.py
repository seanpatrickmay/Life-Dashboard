"""Add composite indexes, cascade FKs, SleepSession constraints, and time_horizon CHECK.

Addresses database persistence layer audit findings:
- Composite indexes on nutrition_intake, journal_entry, imessage_message
- CASCADE deletes on project_note_todo_ref foreign keys
- SleepSession user_id index and (user_id, metric_date) unique constraint
- CHECK constraint on todo_item.time_horizon

Revision ID: 20260324_audit_indexes_constraints
Revises: 20260322_llm_fallback_tracking
Create Date: 2026-03-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260324_audit_indexes_constraints"
down_revision = "20260322_llm_fallback_tracking"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- Composite indexes (Issue #2) ---
    ni_indexes = {idx["name"] for idx in inspector.get_indexes("nutrition_intake")}
    if "ix_nutrition_intake_user_id_day_date" not in ni_indexes:
        op.create_index(
            "ix_nutrition_intake_user_id_day_date",
            "nutrition_intake",
            ["user_id", "day_date"],
        )

    je_indexes = {idx["name"] for idx in inspector.get_indexes("journal_entry")}
    if "ix_journal_entry_user_id_local_date" not in je_indexes:
        op.create_index(
            "ix_journal_entry_user_id_local_date",
            "journal_entry",
            ["user_id", "local_date"],
        )

    im_indexes = {idx["name"] for idx in inspector.get_indexes("imessage_message")}
    if "ix_imessage_message_conversation_id_sent_at_utc" not in im_indexes:
        op.create_index(
            "ix_imessage_message_conversation_id_sent_at_utc",
            "imessage_message",
            ["conversation_id", "sent_at_utc"],
        )

    # --- CASCADE on project_note_todo_ref FKs (Issue #3) ---
    table_names = set(inspector.get_table_names())
    if "project_note_todo_ref" in table_names:
        fks = inspector.get_foreign_keys("project_note_todo_ref")
        fk_names = {fk["name"] for fk in fks if fk.get("name")}

        # Replace note_id FK
        for fk in fks:
            if fk.get("name") and fk["referred_table"] == "project_note":
                op.drop_constraint(fk["name"], "project_note_todo_ref", type_="foreignkey")
                op.create_foreign_key(
                    "fk_project_note_todo_ref_note_id",
                    "project_note_todo_ref",
                    "project_note",
                    ["note_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                break

        # Replace todo_id FK
        for fk in fks:
            if fk.get("name") and fk["referred_table"] == "todo_item":
                op.drop_constraint(fk["name"], "project_note_todo_ref", type_="foreignkey")
                op.create_foreign_key(
                    "fk_project_note_todo_ref_todo_id",
                    "project_note_todo_ref",
                    "todo_item",
                    ["todo_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                break

    # --- SleepSession indexes (Issue #6) ---
    ss_indexes = {idx["name"] for idx in inspector.get_indexes("sleep_session")}
    if "ix_sleep_session_user_id" not in ss_indexes:
        op.create_index("ix_sleep_session_user_id", "sleep_session", ["user_id"])

    ss_constraints = {
        c["name"] for c in inspector.get_unique_constraints("sleep_session")
    }
    if "uq_sleep_session_user_date" not in ss_constraints:
        op.create_unique_constraint(
            "uq_sleep_session_user_date",
            "sleep_session",
            ["user_id", "metric_date"],
        )

    # --- time_horizon CHECK constraint (Issue #7) ---
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_todo_item_time_horizon'
                ) THEN
                    ALTER TABLE todo_item
                    ADD CONSTRAINT ck_todo_item_time_horizon
                    CHECK (time_horizon IN ('this_week', 'this_month', 'this_year'));
                END IF;
            END
            $$;
            """
        )
    )


def downgrade() -> None:
    # --- time_horizon CHECK ---
    op.execute(
        sa.text(
            "ALTER TABLE todo_item DROP CONSTRAINT IF EXISTS ck_todo_item_time_horizon"
        )
    )

    # --- SleepSession ---
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    ss_constraints = {
        c["name"] for c in inspector.get_unique_constraints("sleep_session")
    }
    if "uq_sleep_session_user_date" in ss_constraints:
        op.drop_constraint("uq_sleep_session_user_date", "sleep_session", type_="unique")

    ss_indexes = {idx["name"] for idx in inspector.get_indexes("sleep_session")}
    if "ix_sleep_session_user_id" in ss_indexes:
        op.drop_index("ix_sleep_session_user_id", table_name="sleep_session")

    # --- CASCADE FKs -> revert to plain FKs ---
    table_names = set(inspector.get_table_names())
    if "project_note_todo_ref" in table_names:
        fks = inspector.get_foreign_keys("project_note_todo_ref")
        for fk in fks:
            if fk.get("name") and fk["referred_table"] == "project_note":
                op.drop_constraint(fk["name"], "project_note_todo_ref", type_="foreignkey")
                op.create_foreign_key(
                    None,
                    "project_note_todo_ref",
                    "project_note",
                    ["note_id"],
                    ["id"],
                )
                break
        # Re-read FKs after modification
        inspector = sa.inspect(bind)
        fks = inspector.get_foreign_keys("project_note_todo_ref")
        for fk in fks:
            if fk.get("name") and fk["referred_table"] == "todo_item":
                op.drop_constraint(fk["name"], "project_note_todo_ref", type_="foreignkey")
                op.create_foreign_key(
                    None,
                    "project_note_todo_ref",
                    "todo_item",
                    ["todo_id"],
                    ["id"],
                )
                break

    # --- Composite indexes ---
    im_indexes = {idx["name"] for idx in inspector.get_indexes("imessage_message")}
    if "ix_imessage_message_conversation_id_sent_at_utc" in im_indexes:
        op.drop_index(
            "ix_imessage_message_conversation_id_sent_at_utc",
            table_name="imessage_message",
        )

    je_indexes = {idx["name"] for idx in inspector.get_indexes("journal_entry")}
    if "ix_journal_entry_user_id_local_date" in je_indexes:
        op.drop_index(
            "ix_journal_entry_user_id_local_date",
            table_name="journal_entry",
        )

    ni_indexes = {idx["name"] for idx in inspector.get_indexes("nutrition_intake")}
    if "ix_nutrition_intake_user_id_day_date" in ni_indexes:
        op.drop_index(
            "ix_nutrition_intake_user_id_day_date",
            table_name="nutrition_intake",
        )
