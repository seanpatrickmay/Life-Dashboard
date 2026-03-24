"""Add channel_token column to google_calendar for webhook authentication.

Revision ID: 20260324_calendar_channel_token
Revises: 20260322_llm_fallback_tracking
"""

from alembic import op
import sqlalchemy as sa

revision = "20260324_calendar_channel_token"
down_revision = "20260322_llm_fallback_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "google_calendar",
        sa.Column("channel_token", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("google_calendar", "channel_token")
