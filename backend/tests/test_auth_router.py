from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

auth_module_path = Path(__file__).resolve().parents[1] / "app" / "routers" / "auth.py"
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
