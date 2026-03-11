from __future__ import annotations

import asyncio
import importlib
import os
from pathlib import Path
import sys

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/test_db"
os.environ["ADMIN_EMAIL"] = "test@example.com"
os.environ["FRONTEND_URL"] = "http://localhost:4173"
os.environ["GARMIN_PASSWORD_ENCRYPTION_KEY"] = "test-key"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["READINESS_ADMIN_TOKEN"] = "test-token"
os.environ["GOOGLE_CLIENT_ID_LOCAL"] = "test-google-client-id"
os.environ["GOOGLE_CLIENT_SECRET_LOCAL"] = "test-google-client-secret"
os.environ["GOOGLE_REDIRECT_URI_LOCAL"] = "http://localhost:8000/api/auth/google/callback"

for module_name in ("app.main", "app.db.session", "app.core.config"):
    sys.modules.pop(module_name, None)

main = importlib.import_module("app.main")


def run(coro):
    return asyncio.run(coro)


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object] | None]] = []

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        return None

    async def run_sync(self, fn):
        raise AssertionError("startup should not run schema DDL")


class FakeBegin:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self.conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def test_init_database_only_upserts_admin_user(monkeypatch) -> None:
    conn = FakeConnection()

    class FakeEngine:
        def begin(self) -> FakeBegin:
            return FakeBegin(conn)

    monkeypatch.setattr(main, "engine", FakeEngine())

    run(main._init_database())

    assert len(conn.executed) == 1
    statement, params = conn.executed[0]
    assert 'INSERT INTO "user"' in statement
    assert params == {
        "id": 1,
        "email": "test@example.com",
        "name": "Admin",
        "role": "admin",
    }
