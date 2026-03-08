"""Generic workspace models used by the Notion-style projects surface."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class WorkspacePage(Base):
    __tablename__ = "workspace_page"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    parent_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_page.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="page", index=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    show_in_sidebar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    legacy_project_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    legacy_todo_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    legacy_note_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    extra_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    parent: Mapped["WorkspacePage | None"] = relationship(
        remote_side="WorkspacePage.id",
        back_populates="children",
    )
    children: Mapped[list["WorkspacePage"]] = relationship(
        back_populates="parent",
        order_by="WorkspacePage.sort_order.asc()",
    )
    blocks: Mapped[list["WorkspaceBlock"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="WorkspaceBlock.sort_order.asc()",
    )
    database: Mapped["WorkspaceDatabase | None"] = relationship(
        back_populates="page",
        uselist=False,
        cascade="all, delete-orphan",
    )
    property_values: Mapped[list["WorkspacePropertyValue"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
    )


class WorkspaceBlock(Base):
    __tablename__ = "workspace_block"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("workspace_page.id"), nullable=False, index=True)
    parent_block_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_block.id"), nullable=True, index=True
    )
    block_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    page: Mapped[WorkspacePage] = relationship(back_populates="blocks")
    parent: Mapped["WorkspaceBlock | None"] = relationship(
        remote_side="WorkspaceBlock.id",
        back_populates="children",
    )
    children: Mapped[list["WorkspaceBlock"]] = relationship(
        back_populates="parent",
        order_by="WorkspaceBlock.sort_order.asc()",
    )
    links: Mapped[list["WorkspacePageLink"]] = relationship(
        back_populates="block",
        cascade="all, delete-orphan",
    )


class WorkspaceDatabase(Base):
    __tablename__ = "workspace_database"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    page_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_page.id"), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    page: Mapped[WorkspacePage] = relationship(back_populates="database")
    properties: Mapped[list["WorkspaceProperty"]] = relationship(
        back_populates="database",
        cascade="all, delete-orphan",
        order_by="WorkspaceProperty.sort_order.asc()",
    )
    views: Mapped[list["WorkspaceView"]] = relationship(
        back_populates="database",
        cascade="all, delete-orphan",
        order_by="WorkspaceView.sort_order.asc()",
    )
    templates: Mapped[list["WorkspaceTemplate"]] = relationship(
        back_populates="database",
        cascade="all, delete-orphan",
        order_by="WorkspaceTemplate.sort_order.asc()",
    )


class WorkspaceProperty(Base):
    __tablename__ = "workspace_property"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    database_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_database.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    property_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    database: Mapped[WorkspaceDatabase] = relationship(back_populates="properties")
    options: Mapped[list["WorkspacePropertyOption"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        order_by="WorkspacePropertyOption.sort_order.asc()",
    )
    values: Mapped[list["WorkspacePropertyValue"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
    )


class WorkspacePropertyOption(Base):
    __tablename__ = "workspace_property_option"

    property_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_property.id"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    property: Mapped[WorkspaceProperty] = relationship(back_populates="options")


class WorkspacePropertyValue(Base):
    __tablename__ = "workspace_property_value"
    __table_args__ = (UniqueConstraint("page_id", "property_id", name="uq_workspace_page_property"),)

    page_id: Mapped[int] = mapped_column(ForeignKey("workspace_page.id"), nullable=False, index=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_property.id"), nullable=False, index=True
    )
    value_json: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON, nullable=True
    )

    page: Mapped[WorkspacePage] = relationship(back_populates="property_values")
    property: Mapped[WorkspaceProperty] = relationship(back_populates="values")


class WorkspaceView(Base):
    __tablename__ = "workspace_view"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    database_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_database.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    view_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    database: Mapped[WorkspaceDatabase] = relationship(back_populates="views")


class WorkspacePageLink(Base):
    __tablename__ = "workspace_page_link"
    __table_args__ = (
        UniqueConstraint(
            "source_page_id",
            "target_page_id",
            "block_id",
            name="uq_workspace_page_link_source_target_block",
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    source_page_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_page.id"), nullable=False, index=True
    )
    target_page_id: Mapped[int] = mapped_column(
        ForeignKey("workspace_page.id"), nullable=False, index=True
    )
    block_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_block.id"), nullable=True, index=True
    )
    link_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    block: Mapped[WorkspaceBlock | None] = relationship(back_populates="links")


class WorkspaceFavorite(Base):
    __tablename__ = "workspace_favorite"
    __table_args__ = (UniqueConstraint("user_id", "page_id", name="uq_workspace_favorite_user_page"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("workspace_page.id"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WorkspaceRecent(Base):
    __tablename__ = "workspace_recent"
    __table_args__ = (UniqueConstraint("user_id", "page_id", name="uq_workspace_recent_user_page"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("workspace_page.id"), nullable=False, index=True)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkspaceTemplate(Base):
    __tablename__ = "workspace_template"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    database_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_database.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    properties_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    blocks_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)

    database: Mapped[WorkspaceDatabase | None] = relationship(back_populates="templates")


class WorkspaceAsset(Base):
    __tablename__ = "workspace_asset"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_page.id"), nullable=True, index=True
    )
    block_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_block.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

