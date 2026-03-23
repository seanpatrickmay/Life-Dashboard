"""Add recipe_id FK to nutrition_intake for grouping ingredients by meal.

Revision ID: 20260321_intake_recipe_id
Revises: 20260324_ingredient_name_per_user
Create Date: 2026-03-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260321_intake_recipe_id"
down_revision = "20260324_ingredient_name_per_user"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_intake",
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("nutrition_recipes.id"), nullable=True),
    )
    op.create_index("ix_nutrition_intake_recipe_id", "nutrition_intake", ["recipe_id"])


def downgrade() -> None:
    op.drop_index("ix_nutrition_intake_recipe_id", table_name="nutrition_intake")
    op.drop_column("nutrition_intake", "recipe_id")
