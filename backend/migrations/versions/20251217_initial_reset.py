"""Initial reset migration creating all tables and seeding user id=1.

Revision ID: 20251217_initial_reset
Revises: None
Create Date: 2025-12-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from app.db.models import Base
from app.db.models import entities as _entities  # noqa: F401
from app.db.models import nutrition as _nutrition  # noqa: F401
from app.db.models import todo as _todo  # noqa: F401
from app.db.models.entities import PreferredUnits
from app.db.models.nutrition import ScalingRuleType


# revision identifiers, used by Alembic.
revision = "20251217_initial_reset"
down_revision = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def _ensure_pg_enum(bind, name: str, values: list[str]) -> None:
    if bind.dialect.name != "postgresql":
        return
    formatted_values = ", ".join(f"'{value}'" for value in values)
    bind.execute(
        text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
                    CREATE TYPE {name} AS ENUM ({formatted_values});
                END IF;
            END
            $$;
            """
        )
    )


def _drop_pg_enum(bind, name: str) -> None:
    if bind.dialect.name != "postgresql":
        return
    bind.execute(
        text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
                    DROP TYPE {name};
                END IF;
            END
            $$;
            """
        )
    )


def _ensure_all_tables(bind) -> None:
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    missing_tables = [
        table for table in Base.metadata.sorted_tables if table.name not in existing
    ]
    for table in missing_tables:
        table.create(bind, checkfirst=False)
    inspector = sa.inspect(bind)
    remaining = [
        table.name
        for table in Base.metadata.sorted_tables
        if table.name not in inspector.get_table_names()
    ]
    if remaining:
        raise RuntimeError(f"Failed to create tables: {', '.join(sorted(remaining))}")


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_pg_enum(bind, "preferred_units", [unit.value for unit in PreferredUnits])
    _ensure_pg_enum(
        bind, "nutrient_scaling_rule_type", [rule.value for rule in ScalingRuleType]
    )
    Base.metadata.create_all(bind)
    _ensure_all_tables(bind)
    bind.execute(
        text(
            """
        INSERT INTO "user" (id, email, display_name, created_at, updated_at)
        SELECT 1, 'seed@example.com', 'Seed User', now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE id = 1)
        """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
    _drop_pg_enum(bind, "nutrient_scaling_rule_type")
    _drop_pg_enum(bind, "preferred_units")
