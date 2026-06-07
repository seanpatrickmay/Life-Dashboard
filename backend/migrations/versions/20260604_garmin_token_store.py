"""garmin_token_store

Adds the garmin_token table: one row per user holding the Fernet-encrypted
tarball of garth OAuth token files.

Revision ID: 20260604_garmin_token_store
Revises: 20260402_digest_llm_summary
"""

from alembic import op
import sqlalchemy as sa

revision = "20260604_garmin_token_store"
down_revision = "20260402_digest_llm_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "garmin_token" not in tables:
        op.create_table(
            "garmin_token",
            sa.Column("user_id", sa.Integer, primary_key=True, autoincrement=False),
            sa.Column("encrypted_blob", sa.Text, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )


def downgrade() -> None:
    op.drop_table("garmin_token")
