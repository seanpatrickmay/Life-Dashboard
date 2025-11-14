"""Add user profile, energy, and personalized nutrient goal tables."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.utils.timezone import eastern_now
# revision identifiers, used by Alembic.
revision = "20251110_personalized_goals"
down_revision = "20251108_add_nutrient_group_fix"
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


SCALING_RULE_SEED = [
    (
        "runner_endurance",
        "Endurance Runner",
        "Boost carbs and iron intake for higher mileage blocks.",
        {"carbohydrates": 1.1, "iron": 1.25, "magnesium": 1.1},
    ),
    (
        "vegetarian",
        "Vegetarian",
        "Increase iron and B12 targets for vegetarian diets.",
        {"iron": 1.1, "vitamin_b12": 1.15},
    ),
    (
        "heat_training",
        "Heat Training",
        "Increase electrolyte goals for hotter sessions.",
        {"sodium": 1.15, "potassium": 1.05},
    ),
]


def _exec_autocommit(bind, statement: str) -> None:
    with bind.engine.connect() as connection:  # type: ignore[attr-defined]
        autocommit_conn = connection.execution_options(isolation_level="AUTOCOMMIT")
        autocommit_conn.execute(sa.text(statement))


def _ensure_enum(bind, name: str, values: tuple[str, ...]) -> sa.Enum:
    escaped_values = ", ".join("'" + value.replace("'", "''") + "'" for value in values)
    statement = f"CREATE TYPE {name} AS ENUM ({escaped_values})"
    try:
        _exec_autocommit(bind, statement)
    except Exception as exc:  # type: ignore[broad-except]
        if "already exists" not in str(exc):
            raise
    return sa.Enum(*values, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    for type_name in ("nutrient_scaling_rule_type", "preferred_units"):
        _exec_autocommit(bind, f"DROP TYPE IF EXISTS {type_name} CASCADE")

    preferred_units = _ensure_enum(bind, "preferred_units", ("metric", "imperial"))
    scaling_rule_type = _ensure_enum(bind, "nutrient_scaling_rule_type", ("catalog", "manual"))

    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("sex", sa.String(length=16), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("current_weight_kg", sa.Float(), nullable=True),
        sa.Column("preferred_units", preferred_units, nullable=False, server_default="metric"),
        sa.Column("daily_energy_delta_kcal", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", name="uq_user_profile_user_id"),
    )

    op.create_table(
        "user_measurement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("weight_kg", sa.Float(), nullable=False),
    )

    op.create_table(
        "daily_energy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("active_kcal", sa.Float(), nullable=True),
        sa.Column("bmr_kcal", sa.Float(), nullable=True),
        sa.Column("total_kcal", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "metric_date", name="uq_daily_energy_user_date"),
    )

    goal_columns = [sa.Column(f"goal_{slug}", sa.Float(), nullable=True) for slug, *_ in NUTRIENT_DEFS]
    op.create_table(
        "nutrition_goal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("computed_from_date", sa.Date(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calorie_source", sa.String(length=64), nullable=True),
        *goal_columns,
        sa.UniqueConstraint("user_id", name="uq_nutrition_goal_user_id"),
    )

    multiplier_columns = [
        sa.Column(f"mult_{slug}", sa.Float(), nullable=False, server_default="1.0")
        for slug, *_ in NUTRIENT_DEFS
    ]
    op.create_table(
        "nutrient_scaling_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("type", scaling_rule_type, nullable=False, server_default="catalog"),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        *multiplier_columns,
        sa.UniqueConstraint("owner_user_id", name="uq_scaling_rule_owner"),
    )

    op.create_table(
        "user_nutrient_scaling_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("nutrient_scaling_rule.id"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "rule_id", name="uq_user_rule"),
    )

    nutrient_user_goals_table = sa.Table(
        "nutrition_user_goals",
        sa.MetaData(),
        sa.Column("user_id", sa.Integer()),
        sa.Column("nutrient_id", sa.Integer()),
        sa.Column("daily_goal", sa.Float()),
    )
    nutrient_table = sa.Table(
        "nutrition_nutrients",
        sa.MetaData(),
        sa.Column("id", sa.Integer()),
        sa.Column("slug", sa.String()),
        sa.Column("default_goal", sa.Float()),
    )

    connection = op.get_bind()

    if connection.dialect.has_table(connection, "nutrition_user_goals"):
        result = connection.execute(
            sa.select(
                nutrient_user_goals_table.c.user_id,
                nutrient_table.c.slug,
                nutrient_table.c.default_goal,
                nutrient_user_goals_table.c.daily_goal,
            ).join(nutrient_table, nutrient_table.c.id == nutrient_user_goals_table.c.nutrient_id)
        )
        rows = result.fetchall()
        if rows:
            manual_rules = {}
            for user_id, slug, default_goal, daily_goal in rows:
                if user_id not in manual_rules:
                    manual_rules[user_id] = {}
                baseline = default_goal or 1
                if baseline == 0:
                    continue
                manual_rules[user_id][slug] = daily_goal / baseline

            scaling_table = sa.Table(
                "nutrient_scaling_rule",
                sa.MetaData(),
                sa.Column("id", sa.Integer()),
                sa.Column("created_at", sa.DateTime(timezone=True)),
                sa.Column("updated_at", sa.DateTime(timezone=True)),
                sa.Column("slug", sa.String()),
                sa.Column("label", sa.String()),
                sa.Column("description", sa.String()),
                sa.Column("type", scaling_rule_type),
                sa.Column("owner_user_id", sa.Integer()),
                *[
                    sa.Column(f"mult_{slug}", sa.Float())
                    for slug, *_ in NUTRIENT_DEFS
                ],
            )

            assignment_table = sa.Table(
                "user_nutrient_scaling_rule",
                sa.MetaData(),
                sa.Column("user_id", sa.Integer()),
                sa.Column("rule_id", sa.Integer()),
            )

            for user_id, multipliers in manual_rules.items():
                insert_values = {
                    "slug": f"user-{user_id}-manual",
                    "label": "Manual",
                    "description": "Migrated manual nutrient adjustments",
                    "type": "manual",
                    "owner_user_id": user_id,
                }
                for slug, *_ in NUTRIENT_DEFS:
                    insert_values[f"mult_{slug}"] = (
                        multipliers.get(slug, 1.0) if slug != "calories" else 1.0
                    )
                stmt = scaling_table.insert().returning(scaling_table.c.id)
                result = connection.execute(stmt, [insert_values])
                rule_id = result.scalar_one()
                connection.execute(
                    assignment_table.insert(),
                    {"user_id": user_id, "rule_id": rule_id},
                )

    scaling_table = sa.Table(
        "nutrient_scaling_rule",
        sa.MetaData(),
        sa.Column("slug", sa.String()),
        sa.Column("label", sa.String()),
        sa.Column("description", sa.String()),
        sa.Column("type", scaling_rule_type),
        sa.Column("owner_user_id", sa.Integer()),
        *[
            sa.Column(f"mult_{slug}", sa.Float())
            for slug, *_ in NUTRIENT_DEFS
        ],
    )

    for slug, label, description, overrides in SCALING_RULE_SEED:
        insert_values = {
            "slug": slug,
            "label": label,
            "description": description,
            "type": "catalog",
            "owner_user_id": None,
        }
        for nutrient_slug, *_ in NUTRIENT_DEFS:
            column_name = f"mult_{nutrient_slug}"
            insert_values[column_name] = overrides.get(nutrient_slug, 1.0)
        connection.execute(
            scaling_table.insert().values(
                **insert_values,
                created_at=eastern_now(),
                updated_at=eastern_now(),
            )
        )

    if connection.dialect.has_table(connection, "nutrition_user_goals"):
        op.drop_table("nutrition_user_goals")


def downgrade() -> None:
    bind = op.get_bind()

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

    op.drop_table("user_nutrient_scaling_rule")
    op.drop_table("nutrient_scaling_rule")
    op.drop_table("nutrition_goal")
    op.drop_table("daily_energy")
    op.drop_table("user_measurement")
    op.drop_table("user_profile")

    _exec_autocommit(bind, "DROP TYPE IF EXISTS nutrient_scaling_rule_type CASCADE")
    _exec_autocommit(bind, "DROP TYPE IF EXISTS preferred_units CASCADE")
