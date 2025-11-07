"""Add AI pillar score columns."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251107_vertex_scores"
down_revision = "20251105_insight_cols"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    with op.batch_alter_table("dailymetric") as batch:
        batch.add_column(sa.Column("insight_hrv_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("insight_rhr_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("insight_sleep_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("insight_training_load_score", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("dailymetric") as batch:
        batch.drop_column("insight_training_load_score")
        batch.drop_column("insight_sleep_score")
        batch.drop_column("insight_rhr_score")
        batch.drop_column("insight_hrv_score")
