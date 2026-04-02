"""ai_digest_items

Revision ID: 20260402_ai_digest_items
Revises: 20260325_project_display_name
"""

from alembic import op
import sqlalchemy as sa

revision = "20260402_ai_digest_items"
down_revision = "20260325_project_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "digest_item" not in tables:
        op.create_table(
            "digest_item",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("url", sa.Text, nullable=False),
            sa.Column("normalized_url", sa.Text, nullable=False),
            sa.Column("title", sa.Text, nullable=False),
            sa.Column("summary", sa.Text, nullable=True),
            sa.Column("source_name", sa.String(100), nullable=False),
            sa.Column("source_feed_url", sa.Text, nullable=False),
            sa.Column("category", sa.String(50), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("content_hash", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("normalized_url", name="uq_digest_item_normalized_url"),
        )
        op.create_index("ix_digest_item_fetched_at", "digest_item", ["fetched_at"])
        op.create_index("ix_digest_item_category", "digest_item", ["category"])


def downgrade() -> None:
    op.drop_index("ix_digest_item_category", table_name="digest_item")
    op.drop_index("ix_digest_item_fetched_at", table_name="digest_item")
    op.drop_table("digest_item")
