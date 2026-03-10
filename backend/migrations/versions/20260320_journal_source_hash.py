"""Add source hash to journal day summaries.

Revision ID: 20260320_journal_source_hash
Revises: 20260319_imessage_contact_identity
Create Date: 2026-03-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_journal_source_hash"
down_revision = "20260319_imessage_contact_identity"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
  bind = op.get_bind()
  inspector = sa.inspect(bind)
  columns = {column["name"] for column in inspector.get_columns("journal_day_summary")}
  if "source_hash" not in columns:
    op.add_column(
      "journal_day_summary",
      sa.Column("source_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
  bind = op.get_bind()
  inspector = sa.inspect(bind)
  columns = {column["name"] for column in inspector.get_columns("journal_day_summary")}
  if "source_hash" in columns:
    op.drop_column("journal_day_summary", "source_hash")
