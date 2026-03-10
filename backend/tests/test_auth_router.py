from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/life_dashboard_test")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("FRONTEND_URL", "http://localhost:4173")
os.environ.setdefault("GARMIN_PASSWORD_ENCRYPTION_KEY", "test-key")
os.environ.setdefault("READINESS_ADMIN_TOKEN", "test-token")

auth_module_path = backend_root / "app" / "routers" / "auth.py"
spec = importlib.util.spec_from_file_location("auth_router", auth_module_path)
assert spec and spec.loader
auth_router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth_router)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router.router, prefix="/api")
    app.dependency_overrides[auth_router.get_optional_current_user] = lambda: None
    return TestClient(app)


def test_auth_me_returns_anonymous_payload_when_not_authenticated() -> None:
    client = build_client()

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {"user": None}
