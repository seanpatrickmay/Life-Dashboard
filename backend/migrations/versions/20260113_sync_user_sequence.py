"""Sync user ID sequence after seed inserts.

Revision ID: 20260113_sync_user_sequence
Revises: 20250120_auth_garmin_quota
Create Date: 2026-01-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20260113_sync_user_sequence"
down_revision = "20250120_auth_garmin_quota"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    if "user" not in inspector.get_table_names():
        return
    bind.execute(
        text(
            """
            DO $$
            DECLARE
                seq_name text;
                max_id bigint;
            BEGIN
                SELECT pg_get_serial_sequence('"user"', 'id') INTO seq_name;
                IF seq_name IS NULL THEN
                    RETURN;
                END IF;
                SELECT MAX(id) INTO max_id FROM "user";
                IF max_id IS NULL THEN
                    EXECUTE format('SELECT setval(%L, 1, false)', seq_name);
                ELSE
                    EXECUTE format('SELECT setval(%L, %s, true)', seq_name, max_id);
                END IF;
            END
            $$;
            """
        )
    )


def downgrade() -> None:
    pass
