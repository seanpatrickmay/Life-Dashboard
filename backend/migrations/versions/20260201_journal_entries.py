"""Add journal entries, summaries, and todo accomplishment fields.

Revision ID: 20260201_journal_entries
Revises: 20260113_sync_user_sequence
Create Date: 2026-02-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260201_journal_entries"
down_revision = "20260113_sync_user_sequence"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "journal_entry" not in table_names:
        op.create_table(
            "journal_entry",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("local_date", sa.Date(), nullable=False),
            sa.Column("time_zone", sa.String(length=64), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_journal_entry_local_date", "journal_entry", ["local_date"], unique=False)
        op.create_index("ix_journal_entry_user_id", "journal_entry", ["user_id"], unique=False)
    else:
        journal_entry_indexes = {idx["name"] for idx in inspector.get_indexes("journal_entry")}
        if "ix_journal_entry_local_date" not in journal_entry_indexes:
            op.create_index("ix_journal_entry_local_date", "journal_entry", ["local_date"], unique=False)
        if "ix_journal_entry_user_id" not in journal_entry_indexes:
            op.create_index("ix_journal_entry_user_id", "journal_entry", ["user_id"], unique=False)

    if "journal_day_summary" not in table_names:
        op.create_table(
            "journal_day_summary",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("local_date", sa.Date(), nullable=False),
            sa.Column("time_zone", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.Column("finalized_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("model_name", sa.String(length=64), nullable=True),
            sa.Column("version", sa.String(length=32), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "local_date", name="uq_journal_day_summary_user_date"),
        )
        op.create_index(
            "ix_journal_day_summary_local_date",
            "journal_day_summary",
            ["local_date"],
            unique=False,
        )
        op.create_index(
            "ix_journal_day_summary_user_id",
            "journal_day_summary",
            ["user_id"],
            unique=False,
        )
    else:
        day_summary_indexes = {idx["name"] for idx in inspector.get_indexes("journal_day_summary")}
        if "ix_journal_day_summary_local_date" not in day_summary_indexes:
            op.create_index(
                "ix_journal_day_summary_local_date",
                "journal_day_summary",
                ["local_date"],
                unique=False,
            )
        if "ix_journal_day_summary_user_id" not in day_summary_indexes:
            op.create_index(
                "ix_journal_day_summary_user_id",
                "journal_day_summary",
                ["user_id"],
                unique=False,
            )
        day_summary_uniques = {
            constraint["name"] for constraint in inspector.get_unique_constraints("journal_day_summary")
        }
        if "uq_journal_day_summary_user_date" not in day_summary_uniques:
            op.create_unique_constraint(
                "uq_journal_day_summary_user_date",
                "journal_day_summary",
                ["user_id", "local_date"],
            )

    todo_columns = {col["name"] for col in inspector.get_columns("todo_item")}
    if "completed_local_date" not in todo_columns:
        op.add_column("todo_item", sa.Column("completed_local_date", sa.Date(), nullable=True))
    if "completed_time_zone" not in todo_columns:
        op.add_column("todo_item", sa.Column("completed_time_zone", sa.String(length=64), nullable=True))
    if "accomplishment_text" not in todo_columns:
        op.add_column("todo_item", sa.Column("accomplishment_text", sa.Text(), nullable=True))
    if "accomplishment_generated_at_utc" not in todo_columns:
        op.add_column(
            "todo_item",
            sa.Column("accomplishment_generated_at_utc", sa.DateTime(timezone=True), nullable=True),
        )
    todo_indexes = {idx["name"] for idx in inspector.get_indexes("todo_item")}
    if "ix_todo_item_completed_local_date" not in todo_indexes:
        op.create_index("ix_todo_item_completed_local_date", "todo_item", ["completed_local_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_todo_item_completed_local_date", table_name="todo_item")
    op.drop_column("todo_item", "accomplishment_generated_at_utc")
    op.drop_column("todo_item", "accomplishment_text")
    op.drop_column("todo_item", "completed_time_zone")
    op.drop_column("todo_item", "completed_local_date")

    op.drop_index("ix_journal_day_summary_user_id", table_name="journal_day_summary")
    op.drop_index("ix_journal_day_summary_local_date", table_name="journal_day_summary")
    op.drop_table("journal_day_summary")

    op.drop_index("ix_journal_entry_user_id", table_name="journal_entry")
    op.drop_index("ix_journal_entry_local_date", table_name="journal_entry")
    op.drop_table("journal_entry")
