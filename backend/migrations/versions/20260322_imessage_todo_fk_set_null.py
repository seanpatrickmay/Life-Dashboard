"""Set iMessage audit todo FK to ON DELETE SET NULL.

Revision ID: 20260322_imessage_todo_fk_set_null
Revises: 20260321_openai_readiness_insight
Create Date: 2026-03-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260322_imessage_todo_fk_set_null"
down_revision = "20260321_openai_readiness_insight"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


TABLE_NAME = "imessage_action_audit"
CONSTRAINT_NAME = "imessage_action_audit_target_todo_id_fkey"


def _constraint_options(bind) -> dict[str, str] | None:
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(TABLE_NAME):
        if fk.get("name") == CONSTRAINT_NAME:
            return fk.get("options") or {}
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE_NAME not in tables or "todo_item" not in tables:
        return

    options = _constraint_options(bind)
    if options.get("ondelete") == "SET NULL":
        return

    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT_NAME,
        TABLE_NAME,
        "todo_item",
        ["target_todo_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE_NAME not in tables or "todo_item" not in tables:
        return

    if _constraint_options(bind) is None:
        return

    op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT_NAME,
        TABLE_NAME,
        "todo_item",
        ["target_todo_id"],
        ["id"],
    )
