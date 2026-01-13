"""Add auth, Garmin connection, and chat quota tables.

Revision ID: 20250120_auth_garmin_quota
Revises: 20251217_initial_reset
Create Date: 2025-01-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20250120_auth_garmin_quota"
down_revision = "20251217_initial_reset"
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


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_pg_enum(bind, "user_role", ["admin", "user"])
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    user_columns = (
        {col["name"] for col in inspector.get_columns("user")} if "user" in tables else set()
    )
    user_indexes = (
        {idx["name"] for idx in inspector.get_indexes("user")} if "user" in tables else set()
    )
    if "google_sub" not in user_columns:
        op.add_column("user", sa.Column("google_sub", sa.String(length=255), nullable=True))
    if "email_verified" not in user_columns:
        op.add_column(
            "user",
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
    if "role" not in user_columns:
        op.add_column(
            "user",
            sa.Column(
                "role",
                sa.Enum("admin", "user", name="user_role"),
                nullable=False,
                server_default=sa.text("'user'"),
            ),
        )
    if "google_sub" in user_columns and "ix_user_google_sub" not in user_indexes:
        op.create_index("ix_user_google_sub", "user", ["google_sub"], unique=True)
    if "ix_user_email" not in user_indexes:
        op.create_index("ix_user_email", "user", ["email"], unique=True)
    if "email_verified" in user_columns:
        op.execute(text('UPDATE "user" SET email_verified = false WHERE email_verified IS NULL'))
    if "role" in user_columns:
        op.execute(text('UPDATE "user" SET role = \'user\' WHERE role IS NULL'))

    if "user_session" not in tables:
        op.create_table(
            "user_session",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("remember_me", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.UniqueConstraint("token_hash", name="uq_user_session_token"),
        )
        op.create_index("ix_user_session_user_id", "user_session", ["user_id"])
        op.create_index("ix_user_session_token_hash", "user_session", ["token_hash"])

    if "garmin_connection" not in tables:
        op.create_table(
            "garmin_connection",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("garmin_email", sa.String(length=255), nullable=False),
            sa.Column("encrypted_password", sa.Text(), nullable=False),
            sa.Column("encryption_key_id", sa.String(length=64), nullable=True),
            sa.Column("token_store_path", sa.String(length=512), nullable=False),
            sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("requires_reauth", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.UniqueConstraint("user_id", name="uq_garmin_connection_user"),
        )

    if "chat_usage" not in tables:
        op.create_table(
            "chat_usage",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("usage_date", sa.Date(), nullable=False),
            sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("user_id", "usage_date", name="uq_chat_usage_user_date"),
        )
        op.create_index("ix_chat_usage_user_id", "chat_usage", ["user_id"])

    if "activity" in tables:
        if bind.dialect.name == "postgresql":
            op.execute('ALTER TABLE activity DROP CONSTRAINT IF EXISTS activity_garmin_id_key')
        activity_uniques = {
            constraint["name"] for constraint in inspector.get_unique_constraints("activity")
        }
        if "uq_activity_user_garmin" not in activity_uniques:
            op.create_unique_constraint(
                "uq_activity_user_garmin",
                "activity",
                ["user_id", "garmin_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_constraint("uq_activity_user_garmin", "activity", type_="unique")
    if bind.dialect.name == "postgresql":
        op.execute('ALTER TABLE activity ADD CONSTRAINT activity_garmin_id_key UNIQUE (garmin_id)')

    op.drop_index("ix_chat_usage_user_id", table_name="chat_usage")
    op.drop_table("chat_usage")

    op.drop_table("garmin_connection")

    op.drop_index("ix_user_session_token_hash", table_name="user_session")
    op.drop_index("ix_user_session_user_id", table_name="user_session")
    op.drop_table("user_session")

    op.drop_index("ix_user_google_sub", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_column("user", "role")
    op.drop_column("user", "email_verified")
    op.drop_column("user", "google_sub")
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS user_role")
