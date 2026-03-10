from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.models import (
    WorkspaceCreateBlockInput,
    WorkspaceCreateDatabaseRowInput,
    WorkspaceCreatePageInput,
    WorkspaceUpdateBlockInput,
    WorkspaceUpdatePageInput,
    WorkspaceUpdatePropertiesInput,
)
from mcp_server.runtime import LifeDashboardMcpRuntime


def register_workspace_tools(server: FastMCP, runtime: LifeDashboardMcpRuntime) -> None:
    @server.tool(
        description="Return workspace bootstrap metadata, sidebar pages, favorites, recents, trash, and databases.",
        structured_output=True,
    )
    async def workspace_bootstrap() -> dict[str, Any]:
        return await runtime.workspace_bootstrap()

    @server.tool(
        description="Return one workspace page with blocks, properties, children, and linked databases.",
        structured_output=True,
    )
    async def workspace_get_page(page_id: int) -> dict[str, Any]:
        return await runtime.workspace_get_page(page_id)

    @server.tool(
        description="Return backlinks for one workspace page.", structured_output=True
    )
    async def workspace_get_backlinks(page_id: int) -> dict[str, Any]:
        return await runtime.workspace_get_backlinks(page_id)

    @server.tool(
        description="Search the workspace by title and block text.",
        structured_output=True,
    )
    async def workspace_search(query: str) -> dict[str, Any]:
        return await runtime.workspace_search(query)

    @server.tool(description="Create a new workspace page.", structured_output=True)
    async def workspace_create_page(
        payload: WorkspaceCreatePageInput,
    ) -> dict[str, Any]:
        return await runtime.workspace_create_page(payload)

    @server.tool(
        description="Update a workspace page. Provide only the fields you want to change in updates.",
        structured_output=True,
    )
    async def workspace_update_page(
        page_id: int, updates: WorkspaceUpdatePageInput
    ) -> dict[str, Any]:
        return await runtime.workspace_update_page(page_id, updates)

    @server.tool(
        description="Permanently delete a workspace page.", structured_output=True
    )
    async def workspace_delete_page(page_id: int) -> dict[str, Any]:
        return await runtime.workspace_delete_page(page_id)

    @server.tool(description="Create a block on a page.", structured_output=True)
    async def workspace_create_block(
        payload: WorkspaceCreateBlockInput,
    ) -> dict[str, Any]:
        return await runtime.workspace_create_block(payload)

    @server.tool(description="Update one workspace block.", structured_output=True)
    async def workspace_update_block(
        block_id: int, updates: WorkspaceUpdateBlockInput
    ) -> dict[str, Any]:
        return await runtime.workspace_update_block(block_id, updates)

    @server.tool(description="Delete one workspace block.", structured_output=True)
    async def workspace_delete_block(block_id: int) -> dict[str, Any]:
        return await runtime.workspace_delete_block(block_id)

    @server.tool(description="Reorder all blocks on a page.", structured_output=True)
    async def workspace_reorder_blocks(
        page_id: int, ordered_block_ids: list[int]
    ) -> dict[str, Any]:
        return await runtime.workspace_reorder_blocks(page_id, ordered_block_ids)

    @server.tool(
        description="List rows for a workspace database, optionally using a view and relation filter.",
        structured_output=True,
    )
    async def workspace_list_database_rows(
        database_id: int,
        view_id: int | None = None,
        relation_property_slug: str | None = None,
        relation_page_id: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await runtime.workspace_list_database_rows(
            database_id,
            view_id=view_id,
            relation_property_slug=relation_property_slug,
            relation_page_id=relation_page_id,
            offset=offset,
            limit=limit,
        )

    @server.tool(
        description="Create a row in a workspace database.", structured_output=True
    )
    async def workspace_create_database_row(
        database_id: int, payload: WorkspaceCreateDatabaseRowInput
    ) -> dict[str, Any]:
        return await runtime.workspace_create_database_row(database_id, payload)

    @server.tool(
        description="Update property values for a workspace database row.",
        structured_output=True,
    )
    async def workspace_update_properties(
        page_id: int, payload: WorkspaceUpdatePropertiesInput
    ) -> dict[str, Any]:
        return await runtime.workspace_update_properties(page_id, payload)

    @server.tool(
        description="List templates, optionally filtered to one database.",
        structured_output=True,
    )
    async def workspace_list_templates(
        database_id: int | None = None,
    ) -> dict[str, Any]:
        return await runtime.workspace_list_templates(database_id=database_id)
