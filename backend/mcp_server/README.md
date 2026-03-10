# Life Dashboard MCP

Tool-only MCP server for the Life Dashboard workspace and project/task surface.

## Purpose

This server exposes structured tools for:

- project CRUD and summaries
- task CRUD and filtering
- workspace page/block/database operations
- workspace search, backlinks, and templates

It does not expose generic MCP resources or generic MCP resource templates. Empty results from `list_mcp_resources` and `list_mcp_resource_templates` are expected.

## User Selection

The runtime resolves the workspace user in this order:

1. `MCP_USER_ID`
2. `MCP_USER_EMAIL`
3. `ADMIN_EMAIL`

Use `MCP_USER_ID` when you need deterministic access to a specific user workspace.

## Tool Groups

Project/task tools:

- `list_projects`
- `get_project`
- `create_project`
- `update_project`
- `list_tasks`
- `create_task`
- `update_task`
- `search_projects_and_tasks`

Workspace tools:

- `workspace_bootstrap`
- `workspace_get_page`
- `workspace_get_backlinks`
- `workspace_search`
- `workspace_create_page`
- `workspace_update_page`
- `workspace_delete_page`
- `workspace_create_block`
- `workspace_update_block`
- `workspace_delete_block`
- `workspace_reorder_blocks`
- `workspace_list_database_rows`
- `workspace_create_database_row`
- `workspace_update_properties`
- `workspace_list_templates`

## Recommended Usage

Use the tools in this order when possible:

1. `workspace_bootstrap` to discover the home page, database IDs, views, and sidebar pages.
2. `list_projects` or `list_tasks` for high-level summaries.
3. `workspace_get_page` for page details, blocks, child pages, and property lists.
4. `workspace_list_database_rows` when you need raw row access for a specific database/view.
5. `workspace_list_templates` for workspace templates. This is the template-discovery path; do not expect generic MCP resource-template discovery to return them.

## Troubleshooting

If you see errors like `Future attached to a different loop`, the server was started incorrectly or from an old process. The MCP server must validate startup inside the server lifespan, not in a separate `asyncio.run(...)` call before the server starts.

If you see asyncpg errors such as `another operation is in progress`, restart the MCP server after updating to the fixed startup path and re-run a simple bootstrap call first.

## Smoke Check

Run the smoke check from the backend Poetry environment:

```bash
cd backend
poetry run python ../scripts/check_mcp_server.py
```

Expected behavior:

- exits with code `0`
- prints a compact summary with `home_page_id`, database count, project count, and task count
- fails fast on DB configuration or lifecycle issues
