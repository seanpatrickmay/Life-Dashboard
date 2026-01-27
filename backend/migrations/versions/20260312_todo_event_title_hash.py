"""Add todo text hash to todo_event_link.

Revision ID: 20260312_todo_event_title_hash
Revises: 20260311_todo_deadline
Create Date: 2026-03-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260312_todo_event_title_hash"
down_revision = "20260311_todo_deadline"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "todo_event_link" not in table_names:
        return
    columns = {col["name"] for col in inspector.get_columns("todo_event_link")}
    if "todo_text_hash" not in columns:
        op.add_column(
            "todo_event_link",
            sa.Column("todo_text_hash", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("todo_event_link", "todo_text_hash")
