"""Tests for the Mangum API Gateway handler.

Verifies:
- /health returns 200 {"status":"ok"} via an API GW HTTP API v2 event
- Routing works for an additional public endpoint (/api/time/)
- 404 is returned for unknown paths
- Importing the handler in the local (non-aws) environment does not raise

The test env uses the conftest DATABASE_URL (SQLite) and has no LD_RUNTIME=aws,
so cold_start() runs as a no-op for secrets and builds the local SQLite engine.
/health and /api/time/ need no DB, so they complete without an active connection.
"""
from __future__ import annotations

import importlib
import json
import sys

import pytest


# ---------------------------------------------------------------------------
# Ensure LD_RUNTIME is NOT set to "aws" for these tests (cold_start must
# not fail with the inline job queue validator).
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_aws_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LD_RUNTIME", raising=False)


# ---------------------------------------------------------------------------
# Handler fixture — re-import cleanly so _COLD_STARTED doesn't interfere
# between test runs when the module is already cached from a previous import.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_handler():
    """Import app.aws.api_handler once per module (handler is a module-level singleton)."""
    # Remove both bootstrap and api_handler from cache to ensure clean import
    for mod in ("app.aws.bootstrap", "app.aws.api_handler", "app.aws"):
        sys.modules.pop(mod, None)

    # Reset bootstrap's global flag so cold_start runs fresh
    if "app.aws.bootstrap" in sys.modules:
        sys.modules["app.aws.bootstrap"]._COLD_STARTED = False

    mod = importlib.import_module("app.aws.api_handler")
    return mod


# ---------------------------------------------------------------------------
# Event builder helpers
# ---------------------------------------------------------------------------

def _apigw_event(method: str, path: str, *, source_ip: str = "1.2.3.4") -> dict:
    """Minimal API Gateway HTTP API v2 event."""
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "x"},
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
                "sourceIp": source_ip,
            },
        },
        "isBase64Encoded": False,
    }


def _decode_body(response: dict) -> dict:
    """Decode the Mangum response body (JSON string or base64-encoded bytes)."""
    body = response.get("body") or "{}"
    if response.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode()
    return json.loads(body)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_returns_200(api_handler) -> None:
    """GET /health via Mangum returns 200 with {"status": "ok"}."""
    event = _apigw_event("GET", "/health")
    result = api_handler.handler(event, None)

    assert result["statusCode"] == 200
    body = _decode_body(result)
    assert body == {"status": "ok"}


def test_time_endpoint_returns_200(api_handler) -> None:
    """GET /api/time/ is a public no-auth no-DB endpoint; should return 200."""
    event = _apigw_event("GET", "/api/time/")
    result = api_handler.handler(event, None)

    assert result["statusCode"] == 200
    body = _decode_body(result)
    # The time endpoint returns an ISO timestamp, hour_decimal, moment, and time_zone
    assert "iso" in body
    assert "hour_decimal" in body
    assert "moment" in body
    assert body["moment"] in {"morning", "noon", "twilight", "night"}


def test_unknown_path_returns_404(api_handler) -> None:
    """An unknown path should produce a 404 (FastAPI routing default)."""
    event = _apigw_event("GET", "/this-path-does-not-exist-xyz")
    result = api_handler.handler(event, None)

    assert result["statusCode"] == 404


def test_handler_is_callable(api_handler) -> None:
    """handler must be callable (Mangum wraps FastAPI into a Lambda handler)."""
    assert callable(api_handler.handler)
