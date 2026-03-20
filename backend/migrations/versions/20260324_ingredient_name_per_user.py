"""Change nutrition_foods name unique index from global to per-user.

Revision ID: 20260324_ingredient_name_per_user
Revises: 20260319_nutrition_suggestions
Create Date: 2026-03-24
"""
from __future__ import annotations

from alembic import op


revision = "20260324_ingredient_name_per_user"
down_revision = "20260319_nutrition_suggestions"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    # Drop the old global unique index on name (created by unique=True on column).
    op.drop_index("ix_nutrition_foods_name", table_name="nutrition_foods")
    # Create a non-unique index on name for lookups.
    op.create_index("ix_nutrition_foods_name", "nutrition_foods", ["name"])
    # Add composite unique constraint scoped to owner.
    op.create_unique_constraint(
        "uq_nutrition_food_owner_name",
        "nutrition_foods",
        ["owner_user_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_nutrition_food_owner_name", "nutrition_foods", type_="unique")
    op.drop_index("ix_nutrition_foods_name", table_name="nutrition_foods")
    op.create_index("ix_nutrition_foods_name", "nutrition_foods", ["name"], unique=True)
