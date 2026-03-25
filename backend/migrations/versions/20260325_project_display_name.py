"""Add display_name to project for frontend-only renaming.

Revision ID: 20260325_project_display_name
Revises: 20260325_merge_heads
"""

from alembic import op
import sqlalchemy as sa

revision = "20260325_project_display_name"
down_revision = "20260325_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("project")}
    if "display_name" not in cols:
        op.add_column("project", sa.Column("display_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("project", "display_name")
