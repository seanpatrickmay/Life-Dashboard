"""Add structured insight columns to daily metrics."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251105_insight_cols"
down_revision = "20251104_daily_metric_pk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("dailymetric") as batch:
        batch.add_column(sa.Column("insight_greeting", sa.Text(), nullable=True))
        batch.add_column(sa.Column("insight_hrv_value", sa.Float(), nullable=True))
        batch.add_column(sa.Column("insight_hrv_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("insight_rhr_value", sa.Float(), nullable=True))
        batch.add_column(sa.Column("insight_rhr_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("insight_sleep_value_hours", sa.Float(), nullable=True))
        batch.add_column(sa.Column("insight_sleep_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("insight_training_load_value", sa.Float(), nullable=True))
        batch.add_column(sa.Column("insight_training_load_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("insight_morning_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("dailymetric") as batch:
        batch.drop_column("insight_morning_note")
        batch.drop_column("insight_training_load_note")
        batch.drop_column("insight_training_load_value")
        batch.drop_column("insight_sleep_note")
        batch.drop_column("insight_sleep_value_hours")
        batch.drop_column("insight_rhr_note")
        batch.drop_column("insight_rhr_value")
        batch.drop_column("insight_hrv_note")
        batch.drop_column("insight_hrv_value")
        batch.drop_column("insight_greeting")
