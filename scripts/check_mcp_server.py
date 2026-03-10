#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

backend_root = ROOT / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from mcp_server.runtime import LifeDashboardMcpRuntime  # noqa: E402
from mcp_server.server import build_server  # noqa: E402


async def main() -> int:
    runtime = LifeDashboardMcpRuntime()
    server = build_server(runtime)

    async with server._mcp_server.lifespan(server._mcp_server):
        bootstrap = await runtime.workspace_bootstrap()
        projects = await runtime.list_projects(include_archived=True)
        tasks = await runtime.list_tasks(limit=10_000, offset=0)

    print(
        "MCP OK "
        f"home_page_id={bootstrap['home_page_id']} "
        f"sidebar_pages={len(bootstrap['sidebar_pages'])} "
        f"databases={len(bootstrap['databases'])} "
        f"projects={projects['total_count']} "
        f"tasks={tasks['total_count']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print(f"MCP CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
