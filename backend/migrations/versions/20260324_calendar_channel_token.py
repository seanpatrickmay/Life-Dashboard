"""Add channel_token column to google_calendar for webhook authentication.

Revision ID: 20260324_calendar_channel_token
Revises: 20260324_audit_indexes_constraints
"""

from alembic import op
import sqlalchemy as sa

revision = "20260324_calendar_channel_token"
down_revision = "20260324_audit_indexes_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("google_calendar")}
    if "channel_token" not in columns:
        op.add_column(
            "google_calendar",
            sa.Column("channel_token", sa.String(128), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("google_calendar", "channel_token")
