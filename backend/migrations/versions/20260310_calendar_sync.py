"""Add Google Calendar sync tables and todo date-only flag.

Revision ID: 20260310_calendar_sync
Revises: 20260201_journal_entries
Create Date: 2026-03-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260310_calendar_sync"
down_revision = "20260201_journal_entries"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "google_calendar_connection" not in table_names:
        op.create_table(
            "google_calendar_connection",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("encrypted_access_token", sa.Text(), nullable=False),
            sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
            sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scopes", sa.Text(), nullable=True),
            sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("account_email", sa.String(length=255), nullable=True),
            sa.Column("requires_reauth", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_google_calendar_connection_user"),
        )
        op.create_index(
            "ix_google_calendar_connection_user_id",
            "google_calendar_connection",
            ["user_id"],
            unique=False,
        )

    if "google_calendar" not in table_names:
        op.create_table(
            "google_calendar",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("connection_id", sa.Integer(), nullable=True),
            sa.Column("google_id", sa.String(length=512), nullable=False),
            sa.Column("summary", sa.String(length=512), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("time_zone", sa.String(length=128), nullable=True),
            sa.Column("access_role", sa.String(length=64), nullable=True),
            sa.Column("primary", sa.Boolean(), nullable=False),
            sa.Column("selected", sa.Boolean(), nullable=False),
            sa.Column("is_life_dashboard", sa.Boolean(), nullable=False),
            sa.Column("color_id", sa.String(length=32), nullable=True),
            sa.Column("sync_token", sa.Text(), nullable=True),
            sa.Column("channel_id", sa.String(length=128), nullable=True),
            sa.Column("channel_resource_id", sa.String(length=256), nullable=True),
            sa.Column("channel_expiration", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["connection_id"], ["google_calendar_connection.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "google_id", name="uq_google_calendar_user_google"),
        )
        op.create_index("ix_google_calendar_user_id", "google_calendar", ["user_id"], unique=False)

    if "calendar_event" not in table_names:
        op.create_table(
            "calendar_event",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("calendar_id", sa.Integer(), nullable=False),
            sa.Column("google_event_id", sa.String(length=256), nullable=False),
            sa.Column("recurring_event_id", sa.String(length=256), nullable=True),
            sa.Column("ical_uid", sa.String(length=256), nullable=True),
            sa.Column("summary", sa.String(length=512), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("location", sa.Text(), nullable=True),
            sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_all_day", sa.Boolean(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=True),
            sa.Column("visibility", sa.String(length=32), nullable=True),
            sa.Column("transparency", sa.String(length=32), nullable=True),
            sa.Column("updated_at_google", sa.DateTime(timezone=True), nullable=True),
            sa.Column("html_link", sa.String(length=512), nullable=True),
            sa.Column("hangout_link", sa.String(length=512), nullable=True),
            sa.Column("conference_link", sa.String(length=512), nullable=True),
            sa.Column("organizer", sa.JSON(), nullable=True),
            sa.Column("attendees", sa.JSON(), nullable=True),
            sa.Column("raw_payload", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["calendar_id"], ["google_calendar.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("calendar_id", "google_event_id", name="uq_calendar_event_google"),
        )
        op.create_index("ix_calendar_event_user_id", "calendar_event", ["user_id"], unique=False)
        op.create_index("ix_calendar_event_calendar_id", "calendar_event", ["calendar_id"], unique=False)
        op.create_index("ix_calendar_event_start_time", "calendar_event", ["start_time"], unique=False)
        op.create_index("ix_calendar_event_ical_uid", "calendar_event", ["ical_uid"], unique=False)

    if "todo_event_link" not in table_names:
        op.create_table(
            "todo_event_link",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("todo_id", sa.Integer(), nullable=False),
            sa.Column("calendar_id", sa.Integer(), nullable=False),
            sa.Column("google_event_id", sa.String(length=256), nullable=True),
            sa.Column("ical_uid", sa.String(length=256), nullable=True),
            sa.Column("event_start_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("event_end_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["calendar_id"], ["google_calendar.id"]),
            sa.ForeignKeyConstraint(["todo_id"], ["todo_item.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("todo_id", name="uq_todo_event_link_todo"),
            sa.UniqueConstraint(
                "calendar_id", "google_event_id", name="uq_todo_event_link_event"
            ),
        )
        op.create_index("ix_todo_event_link_user_id", "todo_event_link", ["user_id"], unique=False)

    todo_columns = {col["name"] for col in inspector.get_columns("todo_item")}
    if "deadline_is_date_only" not in todo_columns:
        op.add_column(
            "todo_item",
            sa.Column(
                "deadline_is_date_only",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    op.drop_column("todo_item", "deadline_is_date_only")

    op.drop_index("ix_todo_event_link_user_id", table_name="todo_event_link")
    op.drop_table("todo_event_link")

    op.drop_index("ix_calendar_event_ical_uid", table_name="calendar_event")
    op.drop_index("ix_calendar_event_start_time", table_name="calendar_event")
    op.drop_index("ix_calendar_event_calendar_id", table_name="calendar_event")
    op.drop_index("ix_calendar_event_user_id", table_name="calendar_event")
    op.drop_table("calendar_event")

    op.drop_index("ix_google_calendar_user_id", table_name="google_calendar")
    op.drop_table("google_calendar")

    op.drop_index("ix_google_calendar_connection_user_id", table_name="google_calendar_connection")
    op.drop_table("google_calendar_connection")
