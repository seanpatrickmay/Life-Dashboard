"""Ensure todo deadline_is_date_only column exists.

Revision ID: 20260311_add_todo_deadline_date_only
Revises: 20260310_calendar_sync
Create Date: 2026-03-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260311_add_todo_deadline_date_only"
down_revision = "20260310_calendar_sync"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("todo_item")}
    if "deadline_is_date_only" not in columns:
        op.add_column(
            "todo_item",
            sa.Column(
                "deadline_is_date_only",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    op.drop_column("todo_item", "deadline_is_date_only")
