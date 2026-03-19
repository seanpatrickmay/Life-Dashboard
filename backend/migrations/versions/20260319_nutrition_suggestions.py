"""Add nutrition_suggestions table

Revision ID: 20260319_nutrition_suggestions
Revises: 20260323_todo_time_horizon
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "20260319_nutrition_suggestions"
down_revision = "20260323_todo_time_horizon"

def upgrade() -> None:
    op.create_table(
        "nutrition_suggestions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), unique=True, nullable=False),
        sa.Column("suggestions", JSONB, server_default="[]"),
        sa.Column("stale", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("nutrition_suggestions")
