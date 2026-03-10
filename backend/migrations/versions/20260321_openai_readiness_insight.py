"""Rename vertex insight persistence to readiness insight.

Revision ID: 20260321_openai_readiness_insight
Revises: 20260320_journal_source_hash
Create Date: 2026-03-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260321_openai_readiness_insight"
down_revision = "20260320_journal_source_hash"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = set(inspector.get_table_names())
    if "vertexinsight" in tables and "readiness_insight" not in tables:
        op.rename_table("vertexinsight", "readiness_insight")

    metric_columns = {column["name"] for column in inspector.get_columns("dailymetric")}
    if "vertex_insight_id" in metric_columns and "readiness_insight_id" not in metric_columns:
        op.alter_column("dailymetric", "vertex_insight_id", new_column_name="readiness_insight_id")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    metric_columns = {column["name"] for column in inspector.get_columns("dailymetric")}
    if "readiness_insight_id" in metric_columns and "vertex_insight_id" not in metric_columns:
        op.alter_column("dailymetric", "readiness_insight_id", new_column_name="vertex_insight_id")

    tables = set(inspector.get_table_names())
    if "readiness_insight" in tables and "vertexinsight" not in tables:
        op.rename_table("readiness_insight", "vertexinsight")
