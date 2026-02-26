"""Add projects and todo project suggestions.

Revision ID: 20260314_projects_page
Revises: 20260313_ensure_todo_text_hash
Create Date: 2026-03-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260314_projects_page"
down_revision = "20260313_ensure_todo_text_hash"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "project" not in table_names:
        op.create_table(
            "project",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "name", name="uq_project_user_name"),
        )
        op.create_index("ix_project_user_id", "project", ["user_id"], unique=False)
        op.create_index("ix_project_archived", "project", ["archived"], unique=False)

    if "todo_project_suggestion" not in table_names:
        op.create_table(
            "todo_project_suggestion",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("todo_id", sa.Integer(), nullable=False),
            sa.Column("suggested_project_name", sa.String(length=255), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["todo_id"], ["todo_item.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("todo_id", name="uq_todo_project_suggestion_todo"),
        )
        op.create_index(
            "ix_todo_project_suggestion_user_id", "todo_project_suggestion", ["user_id"], unique=False
        )
        op.create_index(
            "ix_todo_project_suggestion_todo_id", "todo_project_suggestion", ["todo_id"], unique=False
        )

    todo_columns = {col["name"] for col in inspector.get_columns("todo_item")}
    if "project_id" not in todo_columns:
        op.add_column(
            "todo_item",
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=True),
        )

    op.execute(
        sa.text(
            """
            INSERT INTO project (created_at, updated_at, user_id, name, notes, archived, sort_order)
            SELECT now(), now(), u.id, 'Inbox', null, false, -100
            FROM "user" u
            WHERE NOT EXISTS (
              SELECT 1
              FROM project p
              WHERE p.user_id = u.id AND lower(p.name) = lower('Inbox')
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE todo_item t
            SET project_id = p.id
            FROM project p
            WHERE t.user_id = p.user_id
              AND lower(p.name) = lower('Inbox')
              AND t.project_id IS NULL
            """
        )
    )
    op.alter_column("todo_item", "project_id", nullable=False)

    todo_indexes = {idx["name"] for idx in inspector.get_indexes("todo_item")}
    if "ix_todo_item_project_id" not in todo_indexes:
        op.create_index("ix_todo_item_project_id", "todo_item", ["project_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    todo_columns = {col["name"] for col in inspector.get_columns("todo_item")}

    if "project_id" in todo_columns:
        todo_indexes = {idx["name"] for idx in inspector.get_indexes("todo_item")}
        if "ix_todo_item_project_id" in todo_indexes:
            op.drop_index("ix_todo_item_project_id", table_name="todo_item")
        op.drop_column("todo_item", "project_id")

    if "todo_project_suggestion" in table_names:
        op.drop_index("ix_todo_project_suggestion_todo_id", table_name="todo_project_suggestion")
        op.drop_index("ix_todo_project_suggestion_user_id", table_name="todo_project_suggestion")
        op.drop_table("todo_project_suggestion")

    if "project" in table_names:
        op.drop_index("ix_project_archived", table_name="project")
        op.drop_index("ix_project_user_id", table_name="project")
        op.drop_table("project")
