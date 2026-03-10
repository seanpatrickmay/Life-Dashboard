from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.runtime import LifeDashboardMcpRuntime
from mcp_server.tools import register_project_tools, register_workspace_tools


def build_server(runtime: LifeDashboardMcpRuntime | None = None) -> FastMCP:
    actual_runtime = runtime or LifeDashboardMcpRuntime()

    @asynccontextmanager
    async def lifespan(_: FastMCP[Any]) -> AsyncIterator[dict[str, Any]]:
        await actual_runtime.validate_startup()
        yield {}

    server = FastMCP("life-dashboard-private", lifespan=lifespan)
    register_project_tools(server, actual_runtime)
    register_workspace_tools(server, actual_runtime)
    return server


def main() -> None:
    runtime = LifeDashboardMcpRuntime()
    build_server(runtime).run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
