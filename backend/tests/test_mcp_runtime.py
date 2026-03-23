from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ["APP_ENV"] = "local"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://life_dashboard:life_dashboard@localhost:5432/life_dashboard"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["GARMIN_PASSWORD_ENCRYPTION_KEY"] = "x" * 32
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["READINESS_ADMIN_TOKEN"] = "test-token"
os.environ["GOOGLE_CLIENT_ID_LOCAL"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET_LOCAL"] = "test-client-secret"
os.environ["GOOGLE_REDIRECT_URI_LOCAL"] = "http://localhost:8000/api/auth/google/callback"

from app.schemas.workspace import (  # noqa: E402
    WorkspaceBlockResponse,
    WorkspaceBootstrapResponse,
    WorkspaceDatabaseSummary,
    WorkspacePageDetailResponse,
    WorkspacePageSummary,
    WorkspacePropertyResponse,
    WorkspacePropertyValueResponse,
    WorkspaceRowResponse,
    WorkspaceSearchResponse,
    WorkspaceSearchResult,
    WorkspaceViewResponse,
)
from mcp_server.runtime import LifeDashboardMcpRuntime  # noqa: E402
from mcp_server import server as server_module  # noqa: E402
from mcp_server.server import build_server  # noqa: E402


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _CapturingSession:
    def __init__(self, value):
        self.value = value
        self.statement = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, statement):
        self.statement = statement
        return _ScalarResult(self.value)


class _SessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self.session


def _page(
    page_id: int,
    title: str,
    *,
    parent_page_id: int | None = None,
    kind: str = "database_row",
) -> WorkspacePageSummary:
    return WorkspacePageSummary.model_validate(
        {
            "id": page_id,
            "parent_page_id": parent_page_id,
            "title": title,
            "kind": kind,
            "icon": None,
            "cover_url": None,
            "description": None,
            "show_in_sidebar": True,
            "sort_order": 0,
            "is_home": False,
            "trashed_at": None,
            "legacy_project_id": None,
            "legacy_todo_id": None,
            "legacy_note_id": None,
            "created_at": "2026-03-08T00:00:00Z",
            "updated_at": "2026-03-08T00:00:00Z",
        }
    )


def _property_value(
    slug: str,
    property_type: str,
    value,
    *,
    property_id: int = 1,
    name: str | None = None,
):
    return WorkspacePropertyValueResponse.model_validate(
        {
            "property_id": property_id,
            "property_slug": slug,
            "property_name": name or slug.replace("_", " ").title(),
            "property_type": property_type,
            "value": value,
        }
    )


def _database(database_id: int, page_id: int, name: str) -> WorkspaceDatabaseSummary:
    return WorkspaceDatabaseSummary.model_validate(
        {
            "id": database_id,
            "page_id": page_id,
            "name": name,
            "description": f"{name} database",
            "icon": None,
            "is_seeded": True,
            "properties": [],
            "views": [],
        }
    )


class _FakeWorkspacePage:
    def __init__(self, page_id: int, legacy_todo_id: int | None = None) -> None:
        self.id = page_id
        self.legacy_todo_id = legacy_todo_id


class _FakeService:
    def __init__(self, session) -> None:
        self.session = session
        self.created_rows: list[dict[str, object]] = []
        self.updated_values: list[dict[str, object]] = []

    async def get_bootstrap(self, user_id: int) -> WorkspaceBootstrapResponse:
        return WorkspaceBootstrapResponse.model_validate(
            {
                "home_page_id": 100,
                "read_only": False,
                "sidebar_pages": [],
                "favorites": [],
                "recent_pages": [],
                "trash_pages": [],
                "databases": [
                    _database(200, 20, "Projects").model_dump(mode="json"),
                    _database(300, 30, "Tasks").model_dump(mode="json"),
                ],
            }
        )

    async def ensure_workspace(
        self, user_id: int, *, sync_legacy: bool = False
    ) -> None:
        return None

    async def _require_database(self, user_id: int, database_id: int):
        if database_id == 200:
            return SimpleNamespace(
                id=200,
                page_id=20,
                name="Projects",
                properties=[],
            )
        return SimpleNamespace(
            id=300,
            page_id=30,
            name="Tasks",
            properties=[],
        )

    def _database_summary(self, database):
        return _database(database.id, database.page_id, database.name)

    async def _query_database_rows(
        self,
        database,
        view,
        *,
        offset: int = 0,
        limit: int = 50,
        relation_property_slug: str | None = None,
        relation_page_id: int | None = None,
    ):
        if database.id == 200:
            rows = [
                WorkspaceRowResponse(
                    page=_page(401, "Inbox", parent_page_id=20),
                    properties=[
                        _property_value("title", "title", "Inbox"),
                        _property_value("status", "select", "active", property_id=2),
                        _property_value("open_tasks", "rollup", 1, property_id=3),
                        _property_value("done_tasks", "rollup", 0, property_id=4),
                    ],
                ),
                WorkspaceRowResponse(
                    page=_page(402, "Archive Me", parent_page_id=20),
                    properties=[
                        _property_value("title", "title", "Archive Me"),
                        _property_value("status", "select", "archived", property_id=2),
                        _property_value("open_tasks", "rollup", 0, property_id=3),
                        _property_value("done_tasks", "rollup", 3, property_id=4),
                    ],
                ),
            ]
        else:
            all_rows = [
                WorkspaceRowResponse(
                    page=_page(501, "Ship first draft", parent_page_id=30),
                    properties=[
                        _property_value("title", "title", "Ship first draft"),
                        _property_value("project", "relation", 401, property_id=2),
                        _property_value("status", "select", "todo", property_id=3),
                        _property_value(
                            "due", "date", (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"), property_id=4
                        ),
                        _property_value("date_only", "checkbox", False, property_id=5),
                        _property_value(
                            "triage_state", "select", "assigned", property_id=6
                        ),
                        _property_value("suggested_project", "text", "", property_id=7),
                        _property_value("accomplishment", "text", "", property_id=8),
                    ],
                ),
                WorkspaceRowResponse(
                    page=_page(502, "Fix regression", parent_page_id=30),
                    properties=[
                        _property_value("title", "title", "Fix regression"),
                        _property_value("project", "relation", 401, property_id=2),
                        _property_value(
                            "status", "select", "in-progress", property_id=3
                        ),
                        _property_value(
                            "due", "date", (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"), property_id=4
                        ),
                        _property_value("date_only", "checkbox", False, property_id=5),
                        _property_value(
                            "triage_state", "select", "assigned", property_id=6
                        ),
                        _property_value("suggested_project", "text", "", property_id=7),
                        _property_value("accomplishment", "text", "", property_id=8),
                    ],
                ),
                WorkspaceRowResponse(
                    page=_page(503, "Done item", parent_page_id=30),
                    properties=[
                        _property_value("title", "title", "Done item"),
                        _property_value("project", "relation", 401, property_id=2),
                        _property_value("status", "select", "done", property_id=3),
                        _property_value("due", "date", None, property_id=4),
                        _property_value("date_only", "checkbox", False, property_id=5),
                        _property_value(
                            "triage_state", "select", "done", property_id=6
                        ),
                        _property_value("suggested_project", "text", "", property_id=7),
                        _property_value(
                            "accomplishment", "text", "Finished it", property_id=8
                        ),
                    ],
                ),
            ]
            rows = [
                row
                for row in all_rows
                if relation_property_slug is None
                or row.properties[1].value == relation_page_id
            ]
        return rows[offset : offset + limit], len(rows)

    async def get_page_detail(
        self, user_id: int, page_id: int
    ) -> WorkspacePageDetailResponse:
        if page_id == 401:
            return WorkspacePageDetailResponse.model_validate(
                {
                    "page": _page(401, "Inbox", parent_page_id=20).model_dump(
                        mode="json"
                    ),
                    "breadcrumbs": [],
                    "children": [
                        _page(
                            801, "Meeting notes", parent_page_id=401, kind="note"
                        ).model_dump(mode="json"),
                        _page(
                            802, "Reference docs", parent_page_id=401, kind="page"
                        ).model_dump(mode="json"),
                    ],
                    "properties": [
                        _property_value("title", "title", "Inbox").model_dump(
                            mode="json"
                        ),
                        _property_value(
                            "status", "select", "active", property_id=2
                        ).model_dump(mode="json"),
                    ],
                    "blocks": [
                        WorkspaceBlockResponse.model_validate(
                            {
                                "id": 9001,
                                "page_id": 401,
                                "parent_block_id": None,
                                "block_type": "paragraph",
                                "sort_order": 0,
                                "text_content": "Project description",
                                "checked": False,
                                "data_json": None,
                                "links": [],
                            }
                        ).model_dump(mode="json")
                    ],
                    "database": _database(200, 20, "Projects").model_dump(mode="json"),
                    "linked_databases": [],
                    "favorite": False,
                }
            )
        return WorkspacePageDetailResponse.model_validate(
            {
                "page": _page(page_id, "Task", parent_page_id=30).model_dump(
                    mode="json"
                ),
                "breadcrumbs": [],
                "children": [],
                "properties": [
                    _property_value("title", "title", "Task").model_dump(mode="json"),
                    _property_value(
                        "status", "select", "todo", property_id=3
                    ).model_dump(mode="json"),
                ],
                "blocks": [],
                "database": _database(300, 30, "Tasks").model_dump(mode="json"),
                "linked_databases": [],
                "favorite": False,
            }
        )

    async def create_database_row(
        self,
        user_id: int,
        database_id: int,
        *,
        title: str,
        properties: dict,
        template_id=None,
    ):
        self.created_rows.append(
            {"database_id": database_id, "title": title, "properties": properties}
        )
        return _FakeWorkspacePage(
            901, legacy_todo_id=77 if database_id == 300 else None
        )

    async def update_property_values(
        self,
        user_id: int,
        page_id: int,
        *,
        values: dict,
        time_zone=None,
        defer_commit=False,
    ):
        self.updated_values.append({"page_id": page_id, "values": values})
        return _FakeWorkspacePage(page_id, legacy_todo_id=77)

    async def search(self, user_id: int, query: str) -> WorkspaceSearchResponse:
        return WorkspaceSearchResponse.model_validate(
            {
                "results": [
                    WorkspaceSearchResult.model_validate(
                        {
                            "page": _page(401, "Inbox", parent_page_id=20).model_dump(
                                mode="json"
                            ),
                            "match": "Inbox",
                        }
                    ).model_dump(mode="json"),
                    WorkspaceSearchResult.model_validate(
                        {
                            "page": _page(
                                501, "Ship first draft", parent_page_id=30
                            ).model_dump(mode="json"),
                            "match": "Ship",
                        }
                    ).model_dump(mode="json"),
                ]
            }
        )


def test_resolve_user_id_prefers_explicit_id(monkeypatch) -> None:
    session = _CapturingSession(11)
    runtime = LifeDashboardMcpRuntime(
        session_factory=_SessionFactory(session),
        settings_obj=SimpleNamespace(admin_email="admin@example.com"),
    )
    monkeypatch.setenv("MCP_USER_ID", "11")
    monkeypatch.setenv("MCP_USER_EMAIL", "ignored@example.com")

    resolved = asyncio.run(runtime.resolve_user_id())

    assert resolved == 11
    assert 'WHERE "user".id = :id_1' in str(session.statement)


def test_resolve_user_id_falls_back_to_admin_email(monkeypatch) -> None:
    session = _CapturingSession(21)
    runtime = LifeDashboardMcpRuntime(
        session_factory=_SessionFactory(session),
        settings_obj=SimpleNamespace(admin_email="admin@example.com"),
    )
    monkeypatch.delenv("MCP_USER_ID", raising=False)
    monkeypatch.delenv("MCP_USER_EMAIL", raising=False)

    resolved = asyncio.run(runtime.resolve_user_id())

    assert resolved == 21
    assert 'WHERE "user".email = :email_1' in str(session.statement)


def test_resolve_user_id_raises_when_user_missing(monkeypatch) -> None:
    session = _CapturingSession(None)
    runtime = LifeDashboardMcpRuntime(
        session_factory=_SessionFactory(session),
        settings_obj=SimpleNamespace(admin_email="missing@example.com"),
    )
    monkeypatch.delenv("MCP_USER_ID", raising=False)
    monkeypatch.delenv("MCP_USER_EMAIL", raising=False)

    try:
        asyncio.run(runtime.resolve_user_id())
    except RuntimeError as exc:
        assert "missing@example.com" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("Expected runtime error when MCP user cannot be resolved")


def test_list_projects_filters_archived_and_keeps_rollups() -> None:
    runtime = LifeDashboardMcpRuntime(
        service_factory=_FakeService,
        session_factory=_SessionFactory(_CapturingSession(1)),
        settings_obj=SimpleNamespace(admin_email="admin@example.com"),
    )
    runtime._user_id = 1

    payload = asyncio.run(runtime.list_projects())

    assert payload["total_count"] == 1
    assert payload["projects"][0]["title"] == "Inbox"
    assert payload["projects"][0]["open_tasks"] == 1


def test_get_project_returns_notes_and_task_buckets() -> None:
    runtime = LifeDashboardMcpRuntime(
        service_factory=_FakeService,
        session_factory=_SessionFactory(_CapturingSession(1)),
        settings_obj=SimpleNamespace(admin_email="admin@example.com"),
    )
    runtime._user_id = 1

    payload = asyncio.run(runtime.get_project(401))

    assert payload["project"]["title"] == "Inbox"
    assert payload["notes"][0]["kind"] == "note"
    assert payload["child_pages"][0]["kind"] == "page"
    assert payload["tasks"]["counts"]["overdue"] == 1
    assert payload["tasks"]["counts"]["in_progress"] == 0
    assert payload["tasks"]["counts"]["done"] == 1


def test_create_task_sets_expected_defaults(monkeypatch) -> None:
    service = _FakeService(None)
    runtime = LifeDashboardMcpRuntime(
        service_factory=lambda session: service,
        session_factory=_SessionFactory(_CapturingSession(1)),
        settings_obj=SimpleNamespace(admin_email="admin@example.com"),
    )
    runtime._user_id = 1
    called = []

    async def fake_run(todo_id: int) -> None:
        called.append(todo_id)

    monkeypatch.setattr(runtime, "_run_todo_project_suggestions", fake_run)

    payload = asyncio.run(runtime.create_task(title="New task", project_id=401))

    assert service.created_rows[0]["database_id"] == 300
    assert service.created_rows[0]["properties"]["project"] == 401
    assert service.created_rows[0]["properties"]["status"] == "todo"
    assert service.created_rows[0]["properties"]["triage_state"] == "assigned"
    assert called == [77]
    assert payload["task"]["id"] == 901


def test_update_task_maps_project_id_to_relation(monkeypatch) -> None:
    service = _FakeService(None)
    runtime = LifeDashboardMcpRuntime(
        service_factory=lambda session: service,
        session_factory=_SessionFactory(_CapturingSession(1)),
        settings_obj=SimpleNamespace(admin_email="admin@example.com"),
    )
    runtime._user_id = 1

    async def fake_run(todo_id: int) -> None:
        return None

    monkeypatch.setattr(runtime, "_run_todo_project_suggestions", fake_run)
    asyncio.run(
        runtime.update_task(501, updates={"status": "done", "project_id": None})
    )

    assert service.updated_values[0]["page_id"] == 501
    assert service.updated_values[0]["values"] == {"status": "done", "project": None}


def test_build_server_registers_project_and_workspace_tools() -> None:
    runtime = LifeDashboardMcpRuntime(
        service_factory=_FakeService,
        session_factory=_SessionFactory(_CapturingSession(1)),
        settings_obj=SimpleNamespace(admin_email="admin@example.com"),
    )

    server = build_server(runtime)
    tool_names = set(server._tool_manager._tools)

    assert "list_projects" in tool_names
    assert "create_task" in tool_names
    assert "workspace_get_page" in tool_names
    assert "workspace_update_properties" in tool_names


def test_build_server_lifespan_validates_startup(monkeypatch) -> None:
    runtime = LifeDashboardMcpRuntime(
        service_factory=_FakeService,
        session_factory=_SessionFactory(_CapturingSession(1)),
        settings_obj=SimpleNamespace(admin_email="admin@example.com"),
    )
    calls: list[str] = []

    async def fake_validate_startup() -> int:
        calls.append("validated")
        return 1

    monkeypatch.setattr(runtime, "validate_startup", fake_validate_startup)
    server = build_server(runtime)

    async def run_lifespan() -> None:
        async with server._mcp_server.lifespan(server._mcp_server):
            assert calls == ["validated"]

    asyncio.run(run_lifespan())

    assert calls == ["validated"]


def test_main_starts_server_without_preflight_validation(monkeypatch) -> None:
    events: list[object] = []

    class FakeRuntime:
        def __init__(self) -> None:
            self.validate_calls = 0
            events.append(("runtime", self))

        async def validate_startup(self) -> int:
            self.validate_calls += 1
            return 1

    class FakeServer:
        def run(self, transport: str = "stdio") -> None:
            events.append(("run", transport))

    def fake_build_server(runtime: FakeRuntime) -> FakeServer:
        events.append(("build_server", runtime))
        return FakeServer()

    monkeypatch.setattr(server_module, "LifeDashboardMcpRuntime", FakeRuntime)
    monkeypatch.setattr(server_module, "build_server", fake_build_server)

    server_module.main()

    runtime = next(value for key, value in events if key == "runtime")
    build_runtime = next(value for key, value in events if key == "build_server")

    assert build_runtime is runtime
    assert runtime.validate_calls == 0
    assert ("run", "stdio") in events
