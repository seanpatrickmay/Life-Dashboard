"""Add nutrient group metadata."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251108_add_nutrient_group"
down_revision = "20251107_nutrition_tables"
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

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'nutrition_nutrient_group') THEN
                    DROP TYPE nutrition_nutrient_group;
                END IF;
            END$$;
            """
        )
    )
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
                'UPDATE nutrition_nutrients SET "group" = CAST(:group AS nutrition_nutrient_group) WHERE slug = :slug'
            ),
            {"group": group, "slug": slug},
        )

    bind.execute(
        sa.text(
            'UPDATE nutrition_nutrients SET "group" = CAST(\'macro\' AS nutrition_nutrient_group) WHERE "group" IS NULL'
        )
    )
    op.alter_column(
        "nutrition_nutrients",
        "group",
        nullable=False,
        existing_type=nutrient_group,
    )


def downgrade() -> None:
    op.drop_column("nutrition_nutrients", "group")
    sa.Enum(name="nutrition_nutrient_group").drop(op.get_bind(), checkfirst=True)
