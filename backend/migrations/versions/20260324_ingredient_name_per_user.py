"""Change nutrition_foods name unique index from global to per-user.

Revision ID: 20260324_ingredient_name_per_user
Revises: 20260319_nutrition_suggestions
Create Date: 2026-03-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260324_ingredient_name_per_user"
down_revision = "20260319_nutrition_suggestions"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("nutrition_foods")}
    # Drop the old global unique index on name (created by unique=True on column).
    if "ix_nutrition_foods_name" in indexes:
        op.drop_index("ix_nutrition_foods_name", table_name="nutrition_foods")
    # Create a non-unique index on name for lookups.
    indexes = {idx["name"] for idx in inspector.get_indexes("nutrition_foods")}
    if "ix_nutrition_foods_name" not in indexes:
        op.create_index("ix_nutrition_foods_name", "nutrition_foods", ["name"])
    # Add composite unique constraint scoped to owner.
    constraints = {c["name"] for c in inspector.get_unique_constraints("nutrition_foods")}
    if "uq_nutrition_food_owner_name" not in constraints:
        op.create_unique_constraint(
            "uq_nutrition_food_owner_name",
            "nutrition_foods",
            ["owner_user_id", "name"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    constraints = {c["name"] for c in inspector.get_unique_constraints("nutrition_foods")}
    if "uq_nutrition_food_owner_name" in constraints:
        op.drop_constraint("uq_nutrition_food_owner_name", "nutrition_foods", type_="unique")

    indexes = {idx["name"] for idx in inspector.get_indexes("nutrition_foods")}
    if "ix_nutrition_foods_name" in indexes:
        op.drop_index("ix_nutrition_foods_name", table_name="nutrition_foods")
    op.create_index("ix_nutrition_foods_name", "nutrition_foods", ["name"], unique=True)
