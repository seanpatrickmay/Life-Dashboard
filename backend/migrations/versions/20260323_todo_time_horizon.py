"""Add time_horizon column to todo_item.

Revision ID: 20260323_todo_time_horizon
Revises: 20260322_imessage_todo_fk_set_null
Create Date: 2026-03-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323_todo_time_horizon"
down_revision = "20260322_imessage_todo_fk_set_null"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "todo_item",
        sa.Column("time_horizon", sa.String(16), nullable=False, server_default="this_week"),
    )
    op.create_index("ix_todo_item_time_horizon", "todo_item", ["time_horizon"])


def downgrade() -> None:
    op.drop_index("ix_todo_item_time_horizon", table_name="todo_item")
    op.drop_column("todo_item", "time_horizon")
