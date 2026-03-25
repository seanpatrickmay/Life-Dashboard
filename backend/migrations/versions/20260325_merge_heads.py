"""Merge migration heads: claude_code_history + calendar_channel_token

Revision ID: 20260325_merge_heads
Revises: 20260324_calendar_channel_token, 20260325_claude_code_history
"""

revision = "20260325_merge_heads"
down_revision = ("20260324_calendar_channel_token", "20260325_claude_code_history")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
