"""Ensure todo_event_link.todo_text_hash exists.

Revision ID: 20260313_ensure_todo_text_hash
Revises: 20260312_todo_event_title_hash
Create Date: 2026-03-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260313_ensure_todo_text_hash"
down_revision = "20260312_todo_event_title_hash"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names(schema="public"))
    if "todo_event_link" not in table_names:
        return
    columns = {
        col["name"] for col in inspector.get_columns("todo_event_link", schema="public")
    }
    if "todo_text_hash" not in columns:
        op.add_column(
            "todo_event_link",
            sa.Column("todo_text_hash", sa.String(length=64), nullable=True),
            schema="public",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names(schema="public"))
    if "todo_event_link" not in table_names:
        return
    columns = {
        col["name"] for col in inspector.get_columns("todo_event_link", schema="public")
    }
    if "todo_text_hash" in columns:
        op.drop_column("todo_event_link", "todo_text_hash", schema="public")
