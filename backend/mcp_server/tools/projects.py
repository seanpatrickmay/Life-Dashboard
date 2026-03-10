from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.models import ProjectUpdateInput, TaskUpdateInput
from mcp_server.runtime import LifeDashboardMcpRuntime


def register_project_tools(server: FastMCP, runtime: LifeDashboardMcpRuntime) -> None:
    @server.tool(
        description="List project rows from the Projects database.",
        structured_output=True,
    )
    async def list_projects(include_archived: bool = False) -> dict[str, Any]:
        return await runtime.list_projects(include_archived=include_archived)

    @server.tool(
        description="Get one project with properties, notes, blocks, and task summary.",
        structured_output=True,
    )
    async def get_project(
        project_id: int,
        include_tasks: bool = True,
        include_notes: bool = True,
    ) -> dict[str, Any]:
        return await runtime.get_project(
            project_id,
            include_tasks=include_tasks,
            include_notes=include_notes,
        )

    @server.tool(
        description="Create a new project row in the Projects database.",
        structured_output=True,
    )
    async def create_project(title: str, status: str = "active") -> dict[str, Any]:
        return await runtime.create_project(title=title, status=status)

    @server.tool(
        description="Update a project row. Provide only the fields you want to change in updates.",
        structured_output=True,
    )
    async def update_project(
        project_id: int, updates: ProjectUpdateInput
    ) -> dict[str, Any]:
        return await runtime.update_project(
            project_id, updates=updates.model_dump(exclude_unset=True)
        )

    @server.tool(
        description="List tasks, optionally filtered by project, status, due date, or overdue state.",
        structured_output=True,
    )
    async def list_tasks(
        project_id: int | None = None,
        status: str | None = None,
        overdue_only: bool = False,
        due_before: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        return await runtime.list_tasks(
            project_id=project_id,
            status=status,
            overdue_only=overdue_only,
            due_before=due_before,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        description="Create a task row in the Tasks database.", structured_output=True
    )
    async def create_task(
        title: str,
        project_id: int | None = None,
        status: str = "todo",
        due: str | None = None,
        date_only: bool = False,
        triage_state: str = "assigned",
    ) -> dict[str, Any]:
        return await runtime.create_task(
            title=title,
            project_id=project_id,
            status=status,
            due=due,
            date_only=date_only,
            triage_state=triage_state,
        )

    @server.tool(
        description="Update a task row. Provide only the fields you want to change in updates.",
        structured_output=True,
    )
    async def update_task(task_id: int, updates: TaskUpdateInput) -> dict[str, Any]:
        return await runtime.update_task(
            task_id, updates=updates.model_dump(exclude_unset=True)
        )

    @server.tool(
        description="Search projects and tasks using the workspace search index.",
        structured_output=True,
    )
    async def search_projects_and_tasks(query: str, limit: int = 20) -> dict[str, Any]:
        return await runtime.search_projects_and_tasks(query=query, limit=limit)
