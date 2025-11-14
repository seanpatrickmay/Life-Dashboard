"""Create nutrition tables."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from app.utils.timezone import eastern_now

# revision identifiers, used by Alembic.
revision = "20251107_nutrition_tables"
down_revision = "20251107_vertex_scores"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


NUTRIENT_DEFS = [
    ("calories", "Calories", "macro", "kcal", "calories_kcal", 2000),
    ("protein", "Protein", "macro", "g", "protein_g", 120),
    ("carbohydrates", "Carbohydrates", "macro", "g", "carbohydrates_g", 250),
    ("fat", "Fat", "macro", "g", "fat_g", 70),
    ("fiber", "Fiber", "macro", "g", "fiber_g", 30),
    ("vitamin_a", "Vitamin A", "micro", "µg RAE", "vitamin_a_ug", 900),
    ("vitamin_c", "Vitamin C", "micro", "mg", "vitamin_c_mg", 90),
    ("vitamin_d", "Vitamin D", "micro", "IU", "vitamin_d_iu", 800),
    ("vitamin_e", "Vitamin E", "micro", "mg", "vitamin_e_mg", 15),
    ("vitamin_k", "Vitamin K", "micro", "µg", "vitamin_k_ug", 120),
    ("vitamin_b1", "Vitamin B1 (Thiamin)", "micro", "mg", "vitamin_b1_mg", 1.2),
    ("vitamin_b2", "Vitamin B2 (Riboflavin)", "micro", "mg", "vitamin_b2_mg", 1.3),
    ("vitamin_b3", "Vitamin B3 (Niacin)", "micro", "mg", "vitamin_b3_mg", 16),
    ("vitamin_b6", "Vitamin B6", "micro", "mg", "vitamin_b6_mg", 1.3),
    ("vitamin_b12", "Vitamin B12", "micro", "µg", "vitamin_b12_ug", 2.4),
    ("folate", "Folate", "micro", "µg", "folate_ug", 400),
    ("choline", "Choline", "micro", "mg", "choline_mg", 550),
    ("calcium", "Calcium", "micro", "mg", "calcium_mg", 1000),
    ("iron", "Iron", "micro", "mg", "iron_mg", 18),
    ("magnesium", "Magnesium", "micro", "mg", "magnesium_mg", 420),
    ("potassium", "Potassium", "micro", "mg", "potassium_mg", 4700),
    ("sodium", "Sodium", "micro", "mg", "sodium_mg", 1500),
    ("zinc", "Zinc", "micro", "mg", "zinc_mg", 11),
    ("selenium", "Selenium", "micro", "µg", "selenium_ug", 55),
]


def _exec_autocommit(statement: str) -> None:
    """Run raw SQL outside the surrounding Alembic transaction."""
    bind = op.get_bind()
    engine = bind.engine
    with engine.connect() as connection:
        autocommit_conn = connection.execution_options(isolation_level="AUTOCOMMIT")
        autocommit_conn.execute(sa.text(statement))


def _ensure_enum(bind, name: str, values: tuple[str, ...]) -> sa.Enum:
    """Create/patch the enum type so it contains at least the provided values."""
    literal_values = ", ".join("'" + value.replace("'", "''") + "'" for value in values)

    type_exists = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": name},
    ).scalar()

    if not type_exists:
        _exec_autocommit(f"CREATE TYPE {name} AS ENUM ({literal_values})")
    else:
        existing_values_result = bind.execute(
            sa.text(
                """
                SELECT e.enumlabel
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = :name
                """
            ),
            {"name": name},
        )
        existing_values = {row[0] for row in existing_values_result}

        # Rename legacy values that only differ by case (e.g., 'MACRO' -> 'macro')
        for desired in values:
            matches = [val for val in existing_values if val.lower() == desired.lower() and val != desired]
            for match in matches:
                _exec_autocommit(f"ALTER TYPE {name} RENAME VALUE '{match}' TO '{desired}'")
                existing_values.remove(match)
                existing_values.add(desired)

        for value in values:
            if value not in existing_values:
                escaped_value = value.replace("'", "''")
                _exec_autocommit(f"ALTER TYPE {name} ADD VALUE '{escaped_value}'")

    return sa.Enum(*values, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    nutrient_category = _ensure_enum(bind, "nutrition_nutrient_category", ("macro", "micro"))
    food_status = _ensure_enum(bind, "nutrition_food_status", ("confirmed", "unconfirmed"))
    intake_source = _ensure_enum(bind, "nutrition_intake_source", ("manual", "claude"))

    if not inspector.has_table("nutrition_food_profiles"):
        op.create_table(
            "nutrition_food_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            *[sa.Column(column_name, sa.Float(), nullable=True) for _, _, _, _, column_name, _ in NUTRIENT_DEFS],
        )

    if not inspector.has_table("nutrition_foods"):
        op.create_table(
            "nutrition_foods",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("name", sa.String(length=255), nullable=False, unique=True),
            sa.Column("default_unit", sa.String(length=64), nullable=False, server_default="serving"),
            sa.Column("status", food_status, nullable=False, server_default="unconfirmed"),
            sa.Column("source", sa.String(length=64), nullable=True),
            sa.Column("profile_id", sa.Integer(), sa.ForeignKey("nutrition_food_profiles.id"), nullable=False),
        )

    if not inspector.has_table("nutrition_nutrients"):
        op.create_table(
            "nutrition_nutrients",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("slug", sa.String(length=50), nullable=False, unique=True, index=True),
            sa.Column("display_name", sa.String(length=120), nullable=False),
            sa.Column("category", nutrient_category, nullable=False),
            sa.Column("unit", sa.String(length=32), nullable=False),
            sa.Column("default_goal", sa.Float(), nullable=False),
        )

    if not inspector.has_table("nutrition_user_goals"):
        op.create_table(
            "nutrition_user_goals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("nutrient_id", sa.Integer(), sa.ForeignKey("nutrition_nutrients.id"), nullable=False),
            sa.Column("daily_goal", sa.Float(), nullable=False),
            sa.UniqueConstraint("user_id", "nutrient_id", name="uq_user_nutrient_goal"),
        )

    if not inspector.has_table("nutrition_intake"):
        op.create_table(
            "nutrition_intake",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("food_id", sa.Integer(), sa.ForeignKey("nutrition_foods.id"), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(length=64), nullable=False),
            sa.Column("day_date", sa.Date(), nullable=False),
            sa.Column("source", intake_source, nullable=False),
            sa.Column("claude_request_id", sa.String(length=64), nullable=True),
        )

    nutrient_table = sa.table(
        "nutrition_nutrients",
        sa.column("slug", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("category", nutrient_category),
        sa.column("unit", sa.String()),
        sa.column("default_goal", sa.Float()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    result = bind.execute(sa.text("SELECT COUNT(*) FROM nutrition_nutrients"))
    (existing_rows,) = result.fetchone()
    if existing_rows == 0:
        now = eastern_now()
        op.bulk_insert(
            nutrient_table,
            [
                {
                    "slug": slug,
                    "display_name": display,
                    "category": category,
                    "unit": unit,
                    "default_goal": goal,
                    "created_at": now,
                    "updated_at": now,
                }
                for slug, display, category, unit, _column, goal in NUTRIENT_DEFS
            ],
        )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("nutrition_intake")
    op.drop_table("nutrition_user_goals")
    op.drop_table("nutrition_nutrients")
    op.drop_table("nutrition_foods")
    op.drop_table("nutrition_food_profiles")

    sa.Enum(name="nutrition_intake_source").drop(bind, checkfirst=True)
    sa.Enum(name="nutrition_food_status").drop(bind, checkfirst=True)
    sa.Enum(name="nutrition_nutrient_category").drop(bind, checkfirst=True)
