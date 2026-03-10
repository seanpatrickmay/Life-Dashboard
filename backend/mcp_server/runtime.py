from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import select

from app.core.config import settings
from app.db.models.entities import User
from app.db.session import AsyncSessionLocal
from app.schemas.workspace import (
    WorkspaceBacklinksResponse,
    WorkspaceBootstrapResponse,
    WorkspaceCreateBlockRequest,
    WorkspaceCreatePageRequest,
    WorkspaceCreateRowRequest,
    WorkspaceDatabaseRowsResponse,
    WorkspacePageDetailResponse,
    WorkspacePageSummary,
    WorkspacePropertyValueResponse,
    WorkspaceRowResponse,
    WorkspaceSearchResponse,
    WorkspaceTemplateResponse,
    WorkspaceUpdateBlockRequest,
    WorkspaceUpdatePageRequest,
    WorkspaceUpdatePropertyValuesRequest,
)
from app.services.todo_project_suggestion_service import TodoProjectSuggestionService
from app.services.workspace_service import WorkspaceService


@dataclass(slots=True)
class DatabaseLocator:
    database_id: int
    page_id: int
    name: str


class LifeDashboardMcpRuntime:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] = AsyncSessionLocal,
        service_factory: Callable[[Any], WorkspaceService] = WorkspaceService,
        settings_obj: Any = settings,
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._settings = settings_obj
        self._user_id: int | None = None
        self._user_lock = asyncio.Lock()
        self._bootstrap_cache: WorkspaceBootstrapResponse | None = None
        self._bootstrap_lock = asyncio.Lock()
        self._databases_by_name: dict[str, DatabaseLocator] = {}

    async def validate_startup(self) -> int:
        return await self.resolve_user_id()

    async def resolve_user_id(self) -> int:
        if self._user_id is not None:
            return self._user_id
        async with self._user_lock:
            if self._user_id is not None:
                return self._user_id
            requested_user_id = os.getenv("MCP_USER_ID", "").strip()
            requested_email = os.getenv("MCP_USER_EMAIL", "").strip()
            if requested_user_id:
                try:
                    user_id = int(requested_user_id)
                except ValueError as exc:  # pragma: no cover - configuration guard
                    raise RuntimeError(
                        f"MCP_USER_ID must be an integer, got {requested_user_id!r}"
                    ) from exc
                async with self._session_factory() as session:
                    result = await session.execute(
                        select(User.id).where(User.id == user_id)
                    )
                    resolved = result.scalar_one_or_none()
                if resolved is None:
                    raise RuntimeError(
                        f"MCP user {user_id} was not found in the database."
                    )
                self._user_id = resolved
                return resolved

            email = requested_email or self._settings.admin_email
            async with self._session_factory() as session:
                result = await session.execute(
                    select(User.id).where(User.email == email)
                )
                resolved = result.scalar_one_or_none()
            if resolved is None:
                raise RuntimeError(
                    f"MCP user with email {email!r} was not found. Set MCP_USER_ID or MCP_USER_EMAIL to an existing user."
                )
            self._user_id = resolved
            return resolved

    async def _call_service(
        self, callback: Callable[[WorkspaceService, int], Any]
    ) -> Any:
        user_id = await self.resolve_user_id()
        async with self._session_factory() as session:
            service = self._service_factory(session)
            return await callback(service, user_id)

    def _invalidate_bootstrap_cache(self) -> None:
        self._bootstrap_cache = None
        self._databases_by_name = {}

    async def _get_bootstrap(
        self, *, force: bool = False
    ) -> WorkspaceBootstrapResponse:
        if self._bootstrap_cache is not None and not force:
            return self._bootstrap_cache
        async with self._bootstrap_lock:
            if self._bootstrap_cache is not None and not force:
                return self._bootstrap_cache
            bootstrap = await self._call_service(
                lambda service, user_id: service.get_bootstrap(user_id)
            )
            self._bootstrap_cache = bootstrap
            self._databases_by_name = {
                database.name.lower(): DatabaseLocator(
                    database_id=database.id,
                    page_id=database.page_id,
                    name=database.name,
                )
                for database in bootstrap.databases
            }
            return bootstrap

    async def _require_database(self, name: str) -> DatabaseLocator:
        await self._get_bootstrap()
        database = self._databases_by_name.get(name.lower())
        if database is None:
            raise RuntimeError(
                f"{name} database was not found in the workspace bootstrap."
            )
        return database

    async def _assert_row_in_database(
        self, page_id: int, database: DatabaseLocator, label: str
    ) -> WorkspacePageDetailResponse:
        detail = await self.workspace_get_page(page_id)
        page = detail["page"]
        if (
            page.get("kind") != "database_row"
            or page.get("parent_page_id") != database.page_id
        ):
            raise RuntimeError(f"Page {page_id} is not a {label} row.")
        return WorkspacePageDetailResponse.model_validate(detail)

    async def _list_database_rows_unfiltered(
        self,
        database_id: int,
        *,
        relation_property_slug: str | None = None,
        relation_page_id: int | None = None,
    ) -> tuple[list[WorkspaceRowResponse], int]:
        async def operation(
            service: WorkspaceService, user_id: int
        ) -> tuple[list[WorkspaceRowResponse], int]:
            await service.ensure_workspace(user_id)
            database = await service._require_database(user_id, database_id)
            rows: list[WorkspaceRowResponse] = []
            offset = 0
            total_count = 0
            while True:
                batch, total_count = await service._query_database_rows(
                    database,
                    None,
                    offset=offset,
                    limit=100,
                    relation_property_slug=relation_property_slug,
                    relation_page_id=relation_page_id,
                )
                rows.extend(batch)
                offset += len(batch)
                if not batch or offset >= total_count:
                    break
            return rows, total_count

        return await self._call_service(operation)

    async def _run_todo_project_suggestions(self, todo_id: int) -> None:
        user_id = await self.resolve_user_id()
        async with self._session_factory() as session:
            await TodoProjectSuggestionService(session).process_todo_ids(
                user_id=user_id, todo_ids=[todo_id]
            )

    def _property_map(
        self, properties: list[WorkspacePropertyValueResponse]
    ) -> dict[str, Any]:
        return {
            property_value.property_slug: property_value.value
            for property_value in properties
        }

    def _page_summary(self, page: WorkspacePageSummary) -> dict[str, Any]:
        return page.model_dump(mode="json")

    def _project_row_to_record(self, row: WorkspaceRowResponse) -> dict[str, Any]:
        properties = self._property_map(row.properties)
        return {
            "id": row.page.id,
            "title": row.page.title,
            "status": properties.get("status") or "active",
            "open_tasks": properties.get("open_tasks") or 0,
            "done_tasks": properties.get("done_tasks") or 0,
            "icon": row.page.icon,
            "description": row.page.description,
            "page": self._page_summary(row.page),
        }

    def _task_row_to_record(self, row: WorkspaceRowResponse) -> dict[str, Any]:
        properties = self._property_map(row.properties)
        return {
            "id": row.page.id,
            "title": row.page.title,
            "status": properties.get("status") or "todo",
            "project_id": properties.get("project"),
            "due": properties.get("due"),
            "date_only": bool(properties.get("date_only")),
            "triage_state": properties.get("triage_state") or "unassigned",
            "suggested_project": properties.get("suggested_project") or "",
            "accomplishment": properties.get("accomplishment") or "",
            "icon": row.page.icon,
            "description": row.page.description,
            "page": self._page_summary(row.page),
        }

    def _parse_due_datetime(self, due: Any) -> datetime | None:
        if not isinstance(due, str) or not due.strip():
            return None
        normalized = due.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    def _apply_task_filters(
        self,
        tasks: list[dict[str, Any]],
        *,
        status: str | None = None,
        overdue_only: bool = False,
        due_before: str | None = None,
    ) -> list[dict[str, Any]]:
        today = datetime.now().astimezone().date()
        due_before_dt = self._parse_due_datetime(due_before)
        filtered: list[dict[str, Any]] = []
        for task in tasks:
            task_status = str(task.get("status") or "todo")
            due_dt = self._parse_due_datetime(task.get("due"))
            due_local_date = due_dt.astimezone().date() if due_dt is not None else None
            is_overdue = (
                task_status != "done"
                and due_local_date is not None
                and due_local_date < today
            )
            if status and task_status != status:
                continue
            if overdue_only and not is_overdue:
                continue
            if due_before_dt is not None and (due_dt is None or due_dt > due_before_dt):
                continue
            filtered.append(task)
        return filtered

    def _task_bucket_summary(self, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        today = datetime.now().astimezone().date()
        overdue: list[dict[str, Any]] = []
        in_progress: list[dict[str, Any]] = []
        up_next: list[dict[str, Any]] = []
        open_count = 0
        done_count = 0

        def due_key(task: dict[str, Any]) -> tuple[int, Any]:
            due_dt = self._parse_due_datetime(task.get("due"))
            if due_dt is None:
                return (1, "")
            return (0, due_dt.isoformat())

        for task in tasks:
            status = str(task.get("status") or "todo")
            due_dt = self._parse_due_datetime(task.get("due"))
            due_local_date = due_dt.astimezone().date() if due_dt is not None else None
            is_overdue = (
                status != "done"
                and due_local_date is not None
                and due_local_date < today
            )

            if status == "done":
                done_count += 1
                continue

            open_count += 1
            if is_overdue:
                overdue.append(task)
            elif status == "in-progress":
                in_progress.append(task)
            elif status == "todo":
                up_next.append(task)

        overdue.sort(key=due_key)
        in_progress.sort(key=due_key)
        up_next.sort(key=due_key)

        return {
            "counts": {
                "overdue": len(overdue),
                "in_progress": len(in_progress),
                "open": open_count,
                "done": done_count,
            },
            "overdue": overdue,
            "in_progress": in_progress,
            "up_next": up_next,
        }

    async def list_projects(self, *, include_archived: bool = False) -> dict[str, Any]:
        projects_db = await self._require_database("Projects")
        rows, _ = await self._list_database_rows_unfiltered(projects_db.database_id)
        projects = [self._project_row_to_record(row) for row in rows]
        if not include_archived:
            projects = [
                project for project in projects if project.get("status") != "archived"
            ]
        return {
            "projects": projects,
            "total_count": len(projects),
        }

    async def get_project(
        self,
        project_id: int,
        *,
        include_tasks: bool = True,
        include_notes: bool = True,
    ) -> dict[str, Any]:
        projects_db = await self._require_database("Projects")
        await self._assert_row_in_database(project_id, projects_db, "project")
        detail = WorkspacePageDetailResponse.model_validate(
            await self.workspace_get_page(project_id)
        )
        task_rows: list[dict[str, Any]] = []
        task_summary: dict[str, Any] | None = None
        if include_tasks:
            task_rows = (
                await self.list_tasks(project_id=project_id, limit=10_000, offset=0)
            )["tasks"]
            task_summary = self._task_bucket_summary(task_rows)
        note_children = [
            self._page_summary(child)
            for child in detail.children
            if child.kind == "note"
        ]
        child_pages = [
            self._page_summary(child)
            for child in detail.children
            if child.kind != "note"
        ]
        return {
            "project": self._page_summary(detail.page),
            "properties": self._property_map(detail.properties),
            "property_list": [
                property_value.model_dump(mode="json")
                for property_value in detail.properties
            ],
            "blocks": [block.model_dump(mode="json") for block in detail.blocks],
            "notes": note_children if include_notes else [],
            "child_pages": child_pages,
            "tasks": task_summary if include_tasks else None,
        }

    async def create_project(
        self, *, title: str, status: str = "active"
    ) -> dict[str, Any]:
        projects_db = await self._require_database("Projects")
        page = await self._call_service(
            lambda service, user_id: service.create_database_row(
                user_id,
                projects_db.database_id,
                title=title,
                properties={"status": status},
            )
        )
        self._invalidate_bootstrap_cache()
        return await self.get_project(page.id)

    async def update_project(
        self, project_id: int, *, updates: dict[str, Any]
    ) -> dict[str, Any]:
        projects_db = await self._require_database("Projects")
        await self._assert_row_in_database(project_id, projects_db, "project")
        page_updates = {
            key: updates[key]
            for key in ("title", "favorite", "trashed")
            if key in updates
        }
        property_updates = {key: updates[key] for key in ("status",) if key in updates}
        if page_updates:
            await self._call_service(
                lambda service, user_id: service.update_page(
                    user_id, project_id, **page_updates
                )
            )
        if property_updates:
            await self._call_service(
                lambda service, user_id: service.update_property_values(
                    user_id, project_id, values=property_updates
                )
            )
        if page_updates or property_updates:
            self._invalidate_bootstrap_cache()
        return await self.get_project(project_id)

    async def list_tasks(
        self,
        *,
        project_id: int | None = None,
        status: str | None = None,
        overdue_only: bool = False,
        due_before: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        tasks_db = await self._require_database("Tasks")
        if project_id is not None:
            projects_db = await self._require_database("Projects")
            await self._assert_row_in_database(project_id, projects_db, "project")
        rows, _ = await self._list_database_rows_unfiltered(
            tasks_db.database_id,
            relation_property_slug="project" if project_id is not None else None,
            relation_page_id=project_id,
        )
        tasks = [self._task_row_to_record(row) for row in rows]
        filtered = self._apply_task_filters(
            tasks, status=status, overdue_only=overdue_only, due_before=due_before
        )
        paged = filtered[offset : offset + limit]
        return {
            "tasks": paged,
            "total_count": len(filtered),
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(paged) < len(filtered),
        }

    async def create_task(
        self,
        *,
        title: str,
        project_id: int | None = None,
        status: str = "todo",
        due: str | None = None,
        date_only: bool = False,
        triage_state: str = "assigned",
    ) -> dict[str, Any]:
        tasks_db = await self._require_database("Tasks")
        if project_id is not None:
            projects_db = await self._require_database("Projects")
            await self._assert_row_in_database(project_id, projects_db, "project")
        properties: dict[str, Any] = {
            "status": status,
            "triage_state": triage_state,
            "date_only": date_only,
        }
        if project_id is not None:
            properties["project"] = project_id
        if due is not None:
            properties["due"] = due
        page = await self._call_service(
            lambda service, user_id: service.create_database_row(
                user_id,
                tasks_db.database_id,
                title=title,
                properties=properties,
            )
        )
        if getattr(page, "legacy_todo_id", None):
            await self._run_todo_project_suggestions(page.legacy_todo_id)
        return await self._get_task_detail(page.id)

    async def update_task(
        self, task_id: int, *, updates: dict[str, Any]
    ) -> dict[str, Any]:
        tasks_db = await self._require_database("Tasks")
        await self._assert_row_in_database(task_id, tasks_db, "task")
        property_updates = {
            key: updates[key]
            for key in ("title", "status", "due", "date_only", "project_id")
            if key in updates
        }
        values: dict[str, Any] = {}
        if "title" in property_updates:
            values["title"] = property_updates["title"]
        if "status" in property_updates:
            values["status"] = property_updates["status"]
        if "due" in property_updates:
            values["due"] = property_updates["due"]
        if "date_only" in property_updates:
            values["date_only"] = property_updates["date_only"]
        if "project_id" in property_updates:
            values["project"] = property_updates["project_id"]
        if values:
            page = await self._call_service(
                lambda service, user_id: service.update_property_values(
                    user_id, task_id, values=values
                )
            )
            if getattr(page, "legacy_todo_id", None) and "title" in values:
                await self._run_todo_project_suggestions(page.legacy_todo_id)
        return await self._get_task_detail(task_id)

    async def _get_task_detail(self, task_id: int) -> dict[str, Any]:
        tasks_db = await self._require_database("Tasks")
        detail = await self._assert_row_in_database(task_id, tasks_db, "task")
        return {
            "task": self._task_row_to_record(
                WorkspaceRowResponse(page=detail.page, properties=detail.properties)
            ),
            "properties": self._property_map(detail.properties),
            "property_list": [
                property_value.model_dump(mode="json")
                for property_value in detail.properties
            ],
            "blocks": [block.model_dump(mode="json") for block in detail.blocks],
        }

    async def search_projects_and_tasks(
        self, *, query: str, limit: int = 20
    ) -> dict[str, Any]:
        bootstrap = await self._get_bootstrap()
        tasks_db = await self._require_database("Tasks")
        projects_db = await self._require_database("Projects")
        search = WorkspaceSearchResponse.model_validate(
            await self.workspace_search(query)
        )
        results = search.results[: max(0, limit)]
        projects: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []
        for result in results:
            page = result.page
            if page.parent_page_id == projects_db.page_id:
                projects.append(
                    {"page": self._page_summary(page), "match": result.match}
                )
            elif page.parent_page_id == tasks_db.page_id:
                tasks.append({"page": self._page_summary(page), "match": result.match})
        return {
            "query": query,
            "projects": projects,
            "tasks": tasks,
            "total_count": len(projects) + len(tasks),
            "workspace_home_page_id": bootstrap.home_page_id,
        }

    async def workspace_bootstrap(self) -> dict[str, Any]:
        return (await self._get_bootstrap()).model_dump(mode="json")

    async def workspace_get_page(self, page_id: int) -> dict[str, Any]:
        detail = await self._call_service(
            lambda service, user_id: service.get_page_detail(user_id, page_id)
        )
        return detail.model_dump(mode="json")

    async def workspace_get_backlinks(self, page_id: int) -> dict[str, Any]:
        backlinks = await self._call_service(
            lambda service, user_id: service.get_page_backlinks(user_id, page_id)
        )
        return backlinks.model_dump(mode="json")

    async def workspace_search(self, query: str) -> dict[str, Any]:
        search = await self._call_service(
            lambda service, user_id: service.search(user_id, query)
        )
        return search.model_dump(mode="json")

    async def workspace_create_page(
        self, payload: WorkspaceCreatePageRequest
    ) -> dict[str, Any]:
        page = await self._call_service(
            lambda service, user_id: service.create_page(
                user_id, **payload.model_dump(exclude_unset=True)
            )
        )
        self._invalidate_bootstrap_cache()
        return await self.workspace_get_page(page.id)

    async def workspace_update_page(
        self, page_id: int, updates: WorkspaceUpdatePageRequest
    ) -> dict[str, Any]:
        page = await self._call_service(
            lambda service, user_id: service.update_page(
                user_id,
                page_id,
                **updates.model_dump(exclude_unset=True),
            )
        )
        if (
            getattr(page, "legacy_todo_id", None)
            and "title" in updates.model_fields_set
        ):
            await self._run_todo_project_suggestions(page.legacy_todo_id)
        self._invalidate_bootstrap_cache()
        return await self.workspace_get_page(page.id)

    async def workspace_delete_page(self, page_id: int) -> dict[str, Any]:
        await self._call_service(
            lambda service, user_id: service.delete_page(user_id, page_id)
        )
        self._invalidate_bootstrap_cache()
        return {"ok": True, "page_id": page_id}

    async def workspace_create_block(
        self, payload: WorkspaceCreateBlockRequest
    ) -> dict[str, Any]:
        await self._call_service(
            lambda service, user_id: service.create_block(
                user_id, **payload.model_dump(exclude_unset=True)
            )
        )
        return await self.workspace_get_page(payload.page_id)

    async def workspace_update_block(
        self, block_id: int, updates: WorkspaceUpdateBlockRequest
    ) -> dict[str, Any]:
        block = await self._call_service(
            lambda service, user_id: service.update_block(
                user_id,
                block_id,
                **updates.model_dump(exclude_unset=True),
            )
        )
        return await self.workspace_get_page(block.page_id)

    async def workspace_delete_block(self, block_id: int) -> dict[str, Any]:
        await self._call_service(
            lambda service, user_id: service.delete_block(user_id, block_id)
        )
        return {"ok": True, "block_id": block_id}

    async def workspace_reorder_blocks(
        self, page_id: int, ordered_block_ids: list[int]
    ) -> dict[str, Any]:
        await self._call_service(
            lambda service, user_id: service.reorder_blocks(
                user_id, page_id, ordered_block_ids
            )
        )
        return {"ok": True, "page_id": page_id, "ordered_block_ids": ordered_block_ids}

    async def workspace_list_database_rows(
        self,
        database_id: int,
        *,
        view_id: int | None = None,
        relation_property_slug: str | None = None,
        relation_page_id: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        rows = await self._call_service(
            lambda service, user_id: service.get_database_rows(
                user_id,
                database_id,
                view_id=view_id,
                offset=offset,
                limit=limit,
                relation_property_slug=relation_property_slug,
                relation_page_id=relation_page_id,
            )
        )
        return rows.model_dump(mode="json")

    async def workspace_create_database_row(
        self, database_id: int, payload: WorkspaceCreateRowRequest
    ) -> dict[str, Any]:
        page = await self._call_service(
            lambda service, user_id: service.create_database_row(
                user_id,
                database_id,
                title=payload.title,
                properties=payload.properties,
                template_id=payload.template_id,
            )
        )
        if getattr(page, "legacy_todo_id", None):
            await self._run_todo_project_suggestions(page.legacy_todo_id)
        self._invalidate_bootstrap_cache()
        return await self.workspace_get_page(page.id)

    async def workspace_update_properties(
        self,
        page_id: int,
        payload: WorkspaceUpdatePropertyValuesRequest,
    ) -> dict[str, Any]:
        page = await self._call_service(
            lambda service, user_id: service.update_property_values(
                user_id, page_id, values=payload.values
            )
        )
        if getattr(page, "legacy_todo_id", None) and "title" in payload.values:
            await self._run_todo_project_suggestions(page.legacy_todo_id)
        self._invalidate_bootstrap_cache()
        return await self.workspace_get_page(page.id)

    async def workspace_list_templates(
        self, *, database_id: int | None = None
    ) -> dict[str, Any]:
        templates = await self._call_service(
            lambda service, user_id: service.list_templates(user_id, database_id)
        )
        return {
            "templates": [
                WorkspaceTemplateResponse.model_validate(template).model_dump(
                    mode="json"
                )
                for template in templates
            ]
        }
