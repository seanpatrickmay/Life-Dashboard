"""Reshape daily metrics to be keyed by day and store additional aggregates."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251104_daily_metric_pk"
down_revision = "expand_garmin_id"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    with op.batch_alter_table("dailymetric") as batch:
        batch.drop_constraint("dailymetric_pkey", type_="primary")
        batch.drop_constraint("uq_daily_metric", type_="unique")
        batch.add_column(sa.Column("training_volume_seconds", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("readiness_narrative", sa.Text(), nullable=True))
        batch.drop_column("id")
        batch.create_primary_key("pk_dailymetric", ["user_id", "metric_date"])


def downgrade() -> None:
    with op.batch_alter_table("dailymetric") as batch:
        batch.drop_constraint("pk_dailymetric", type_="primary")
        batch.add_column(
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=True)
        )
        batch.create_primary_key("dailymetric_pkey", ["id"])
        batch.create_unique_constraint("uq_daily_metric", ["user_id", "metric_date"])
        batch.drop_column("readiness_narrative")
        batch.drop_column("training_volume_seconds")
