"""digest_llm_summary

Revision ID: 20260402_digest_llm_summary
Revises: 20260402_ai_digest_items
"""

from alembic import op
import sqlalchemy as sa

revision = "20260402_digest_llm_summary"
down_revision = "20260402_ai_digest_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("digest_item")}
    if "llm_summary" not in columns:
        op.add_column("digest_item", sa.Column("llm_summary", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("digest_item", "llm_summary")
