"""Track LLM fallback usage in processing runs and action audits.

Revision ID: 20260322_llm_fallback_tracking
Revises: 20260321_intake_recipe_id
Create Date: 2026-03-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260322_llm_fallback_tracking"
down_revision = "20260321_intake_recipe_id"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "imessage_processing_run",
        sa.Column("llm_fallback_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "imessage_action_audit",
        sa.Column("extraction_method", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("imessage_action_audit", "extraction_method")
    op.drop_column("imessage_processing_run", "llm_fallback_count")
