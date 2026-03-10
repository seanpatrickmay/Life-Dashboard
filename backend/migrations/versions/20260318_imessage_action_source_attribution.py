"""Add source attribution timestamp to iMessage action audit.

Revision ID: 20260318_imessage_action_source_attribution
Revises: 20260317_imessage_pipeline
Create Date: 2026-03-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_imessage_action_source_attribution"
down_revision = "20260317_imessage_pipeline"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("imessage_action_audit")}
    if "source_occurred_at_utc" not in columns:
        op.add_column(
            "imessage_action_audit",
            sa.Column("source_occurred_at_utc", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("imessage_action_audit")}
    if "source_occurred_at_utc" in columns:
        op.drop_column("imessage_action_audit", "source_occurred_at_utc")
