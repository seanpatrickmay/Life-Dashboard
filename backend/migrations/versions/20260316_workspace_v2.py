"""Add workspace tables for the Notion-style projects surface.

Revision ID: 20260316_workspace_v2
Revises: 20260314_projects_page
Create Date: 2026-03-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_workspace_v2"
down_revision = "20260314_projects_page"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "workspace_page" not in table_names:
        op.create_table(
            "workspace_page",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("parent_page_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("icon", sa.String(length=64), nullable=True),
            sa.Column("cover_url", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("show_in_sidebar", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_home", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("legacy_project_id", sa.Integer(), nullable=True),
            sa.Column("legacy_todo_id", sa.Integer(), nullable=True),
            sa.Column("legacy_note_id", sa.Integer(), nullable=True),
            sa.Column("extra_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["parent_page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workspace_page_user_id", "workspace_page", ["user_id"], unique=False)
        op.create_index("ix_workspace_page_parent_page_id", "workspace_page", ["parent_page_id"], unique=False)
        op.create_index("ix_workspace_page_kind", "workspace_page", ["kind"], unique=False)
        op.create_index("ix_workspace_page_is_home", "workspace_page", ["is_home"], unique=False)
        op.create_index("ix_workspace_page_legacy_project_id", "workspace_page", ["legacy_project_id"], unique=False)
        op.create_index("ix_workspace_page_legacy_todo_id", "workspace_page", ["legacy_todo_id"], unique=False)
        op.create_index("ix_workspace_page_legacy_note_id", "workspace_page", ["legacy_note_id"], unique=False)

    if "workspace_block" not in table_names:
        op.create_table(
            "workspace_block",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("page_id", sa.Integer(), nullable=False),
            sa.Column("parent_block_id", sa.Integer(), nullable=True),
            sa.Column("block_type", sa.String(length=48), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("text_content", sa.Text(), nullable=False, server_default=""),
            sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("data_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["parent_block_id"], ["workspace_block.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workspace_block_user_id", "workspace_block", ["user_id"], unique=False)
        op.create_index("ix_workspace_block_page_id", "workspace_block", ["page_id"], unique=False)
        op.create_index("ix_workspace_block_parent_block_id", "workspace_block", ["parent_block_id"], unique=False)
        op.create_index("ix_workspace_block_block_type", "workspace_block", ["block_type"], unique=False)

    if "workspace_database" not in table_names:
        op.create_table(
            "workspace_database",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("page_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("icon", sa.String(length=64), nullable=True),
            sa.Column("is_seeded", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("extra_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("page_id"),
        )
        op.create_index("ix_workspace_database_user_id", "workspace_database", ["user_id"], unique=False)
        op.create_index("ix_workspace_database_page_id", "workspace_database", ["page_id"], unique=False)

    if "workspace_property" not in table_names:
        op.create_table(
            "workspace_property",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("database_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("slug", sa.String(length=128), nullable=False),
            sa.Column("property_type", sa.String(length=32), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("config_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["database_id"], ["workspace_database.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workspace_property_user_id", "workspace_property", ["user_id"], unique=False)
        op.create_index("ix_workspace_property_database_id", "workspace_property", ["database_id"], unique=False)
        op.create_index("ix_workspace_property_property_type", "workspace_property", ["property_type"], unique=False)

    if "workspace_property_option" not in table_names:
        op.create_table(
            "workspace_property_option",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("property_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("value", sa.String(length=128), nullable=False),
            sa.Column("color", sa.String(length=32), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["property_id"], ["workspace_property.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workspace_property_option_property_id", "workspace_property_option", ["property_id"], unique=False)

    if "workspace_property_value" not in table_names:
        op.create_table(
            "workspace_property_value",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("page_id", sa.Integer(), nullable=False),
            sa.Column("property_id", sa.Integer(), nullable=False),
            sa.Column("value_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["property_id"], ["workspace_property.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("page_id", "property_id", name="uq_workspace_page_property"),
        )
        op.create_index("ix_workspace_property_value_page_id", "workspace_property_value", ["page_id"], unique=False)
        op.create_index("ix_workspace_property_value_property_id", "workspace_property_value", ["property_id"], unique=False)

    if "workspace_view" not in table_names:
        op.create_table(
            "workspace_view",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("database_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("view_type", sa.String(length=32), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("config_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["database_id"], ["workspace_database.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workspace_view_user_id", "workspace_view", ["user_id"], unique=False)
        op.create_index("ix_workspace_view_database_id", "workspace_view", ["database_id"], unique=False)
        op.create_index("ix_workspace_view_view_type", "workspace_view", ["view_type"], unique=False)

    if "workspace_page_link" not in table_names:
        op.create_table(
            "workspace_page_link",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("source_page_id", sa.Integer(), nullable=False),
            sa.Column("target_page_id", sa.Integer(), nullable=False),
            sa.Column("block_id", sa.Integer(), nullable=True),
            sa.Column("link_text", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["block_id"], ["workspace_block.id"]),
            sa.ForeignKeyConstraint(["source_page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["target_page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "source_page_id",
                "target_page_id",
                "block_id",
                name="uq_workspace_page_link_source_target_block",
            ),
        )
        op.create_index("ix_workspace_page_link_user_id", "workspace_page_link", ["user_id"], unique=False)
        op.create_index("ix_workspace_page_link_source_page_id", "workspace_page_link", ["source_page_id"], unique=False)
        op.create_index("ix_workspace_page_link_target_page_id", "workspace_page_link", ["target_page_id"], unique=False)
        op.create_index("ix_workspace_page_link_block_id", "workspace_page_link", ["block_id"], unique=False)

    if "workspace_favorite" not in table_names:
        op.create_table(
            "workspace_favorite",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("page_id", sa.Integer(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "page_id", name="uq_workspace_favorite_user_page"),
        )
        op.create_index("ix_workspace_favorite_user_id", "workspace_favorite", ["user_id"], unique=False)
        op.create_index("ix_workspace_favorite_page_id", "workspace_favorite", ["page_id"], unique=False)

    if "workspace_recent" not in table_names:
        op.create_table(
            "workspace_recent",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("page_id", sa.Integer(), nullable=False),
            sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "page_id", name="uq_workspace_recent_user_page"),
        )
        op.create_index("ix_workspace_recent_user_id", "workspace_recent", ["user_id"], unique=False)
        op.create_index("ix_workspace_recent_page_id", "workspace_recent", ["page_id"], unique=False)

    if "workspace_template" not in table_names:
        op.create_table(
            "workspace_template",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("database_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("icon", sa.String(length=64), nullable=True),
            sa.Column("cover_url", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("properties_json", sa.JSON(), nullable=True),
            sa.Column("blocks_json", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["database_id"], ["workspace_database.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workspace_template_user_id", "workspace_template", ["user_id"], unique=False)
        op.create_index("ix_workspace_template_database_id", "workspace_template", ["database_id"], unique=False)

    if "workspace_asset" not in table_names:
        op.create_table(
            "workspace_asset",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("page_id", sa.Integer(), nullable=True),
            sa.Column("block_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("mime_type", sa.String(length=128), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("storage_key", sa.String(length=512), nullable=True),
            sa.Column("public_url", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.ForeignKeyConstraint(["block_id"], ["workspace_block.id"]),
            sa.ForeignKeyConstraint(["page_id"], ["workspace_page.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_workspace_asset_user_id", "workspace_asset", ["user_id"], unique=False)
        op.create_index("ix_workspace_asset_page_id", "workspace_asset", ["page_id"], unique=False)
        op.create_index("ix_workspace_asset_block_id", "workspace_asset", ["block_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "workspace_asset" in table_names:
        op.drop_index("ix_workspace_asset_block_id", table_name="workspace_asset")
        op.drop_index("ix_workspace_asset_page_id", table_name="workspace_asset")
        op.drop_index("ix_workspace_asset_user_id", table_name="workspace_asset")
        op.drop_table("workspace_asset")

    if "workspace_template" in table_names:
        op.drop_index("ix_workspace_template_database_id", table_name="workspace_template")
        op.drop_index("ix_workspace_template_user_id", table_name="workspace_template")
        op.drop_table("workspace_template")

    if "workspace_recent" in table_names:
        op.drop_index("ix_workspace_recent_page_id", table_name="workspace_recent")
        op.drop_index("ix_workspace_recent_user_id", table_name="workspace_recent")
        op.drop_table("workspace_recent")

    if "workspace_favorite" in table_names:
        op.drop_index("ix_workspace_favorite_page_id", table_name="workspace_favorite")
        op.drop_index("ix_workspace_favorite_user_id", table_name="workspace_favorite")
        op.drop_table("workspace_favorite")

    if "workspace_page_link" in table_names:
        op.drop_index("ix_workspace_page_link_block_id", table_name="workspace_page_link")
        op.drop_index("ix_workspace_page_link_target_page_id", table_name="workspace_page_link")
        op.drop_index("ix_workspace_page_link_source_page_id", table_name="workspace_page_link")
        op.drop_index("ix_workspace_page_link_user_id", table_name="workspace_page_link")
        op.drop_table("workspace_page_link")

    if "workspace_view" in table_names:
        op.drop_index("ix_workspace_view_view_type", table_name="workspace_view")
        op.drop_index("ix_workspace_view_database_id", table_name="workspace_view")
        op.drop_index("ix_workspace_view_user_id", table_name="workspace_view")
        op.drop_table("workspace_view")

    if "workspace_property_value" in table_names:
        op.drop_index("ix_workspace_property_value_property_id", table_name="workspace_property_value")
        op.drop_index("ix_workspace_property_value_page_id", table_name="workspace_property_value")
        op.drop_table("workspace_property_value")

    if "workspace_property_option" in table_names:
        op.drop_index("ix_workspace_property_option_property_id", table_name="workspace_property_option")
        op.drop_table("workspace_property_option")

    if "workspace_property" in table_names:
        op.drop_index("ix_workspace_property_property_type", table_name="workspace_property")
        op.drop_index("ix_workspace_property_database_id", table_name="workspace_property")
        op.drop_index("ix_workspace_property_user_id", table_name="workspace_property")
        op.drop_table("workspace_property")

    if "workspace_database" in table_names:
        op.drop_index("ix_workspace_database_page_id", table_name="workspace_database")
        op.drop_index("ix_workspace_database_user_id", table_name="workspace_database")
        op.drop_table("workspace_database")

    if "workspace_block" in table_names:
        op.drop_index("ix_workspace_block_block_type", table_name="workspace_block")
        op.drop_index("ix_workspace_block_parent_block_id", table_name="workspace_block")
        op.drop_index("ix_workspace_block_page_id", table_name="workspace_block")
        op.drop_index("ix_workspace_block_user_id", table_name="workspace_block")
        op.drop_table("workspace_block")

    if "workspace_page" in table_names:
        op.drop_index("ix_workspace_page_legacy_note_id", table_name="workspace_page")
        op.drop_index("ix_workspace_page_legacy_todo_id", table_name="workspace_page")
        op.drop_index("ix_workspace_page_legacy_project_id", table_name="workspace_page")
        op.drop_index("ix_workspace_page_is_home", table_name="workspace_page")
        op.drop_index("ix_workspace_page_kind", table_name="workspace_page")
        op.drop_index("ix_workspace_page_parent_page_id", table_name="workspace_page")
        op.drop_index("ix_workspace_page_user_id", table_name="workspace_page")
        op.drop_table("workspace_page")
