"""Ensure nutrition nutrient group column exists."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "20251108_add_nutrient_group_fix"
down_revision = "20251108_add_nutrient_group"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None

NUTRIENT_GROUPS = {
    "calories": "macro",
    "protein": "macro",
    "carbohydrates": "macro",
    "fat": "macro",
    "fiber": "macro",
    "vitamin_a": "vitamin",
    "vitamin_c": "vitamin",
    "vitamin_d": "vitamin",
    "vitamin_e": "vitamin",
    "vitamin_k": "vitamin",
    "vitamin_b1": "vitamin",
    "vitamin_b2": "vitamin",
    "vitamin_b3": "vitamin",
    "vitamin_b6": "vitamin",
    "vitamin_b12": "vitamin",
    "folate": "vitamin",
    "choline": "vitamin",
    "calcium": "mineral",
    "iron": "mineral",
    "magnesium": "mineral",
    "potassium": "mineral",
    "sodium": "mineral",
    "zinc": "mineral",
    "selenium": "mineral",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    has_group = any(
        column["name"] == "group"
        for column in inspector.get_columns("nutrition_nutrients")
    )

    if has_group:
        return

    nutrient_group = sa.Enum(
        "macro", "vitamin", "mineral", name="nutrition_nutrient_group"
    )
    nutrient_group.create(bind, checkfirst=True)

    op.add_column(
        "nutrition_nutrients",
        sa.Column(
            "group",
            nutrient_group,
            nullable=True,
        ),
    )

    for slug, group in NUTRIENT_GROUPS.items():
        bind.execute(
            sa.text(
                'UPDATE nutrition_nutrients SET "group" = :group::nutrition_nutrient_group WHERE slug = :slug'
            ),
            {"group": group, "slug": slug},
        )

    bind.execute(
        sa.text(
            'UPDATE nutrition_nutrients SET "group" = \'macro\'::nutrition_nutrient_group WHERE "group" IS NULL'
        )
    )
    op.alter_column(
        "nutrition_nutrients",
        "group",
        nullable=False,
        existing_type=nutrient_group,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if any(
        column["name"] == "group"
        for column in inspector.get_columns("nutrition_nutrients")
    ):
        op.drop_column("nutrition_nutrients", "group")
    sa.Enum(name="nutrition_nutrient_group").drop(bind, checkfirst=True)
