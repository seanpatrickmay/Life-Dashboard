from __future__ import annotations

from datetime import datetime
from pathlib import Path
import importlib.util
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

time_module_path = backend_root / "app" / "routers" / "time.py"
spec = importlib.util.spec_from_file_location("time_router", time_module_path)
assert spec and spec.loader
time_router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(time_router)


class FixedDateTime(datetime):
    """Helper datetime that always returns a fixed moment."""

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls(2024, 5, 1, 14, 45, 30, tzinfo=tz)


def build_client() -> TestClient:
    """Create a lightweight FastAPI app that only mounts the time router."""
    app = FastAPI()
    app.include_router(time_router.router, prefix="/api")
    return TestClient(app)


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (0, "night"),
        (6, "morning"),
        (10, "morning"),
        (11, "noon"),
        (16, "noon"),
        (17, "twilight"),
        (20, "twilight"),
        (21, "night"),
        (23, "night"),
    ],
)
def test_compute_moment_boundaries(hour: int, expected: str) -> None:
    assert time_router.compute_moment(hour) == expected


def test_time_endpoint_uses_time_zone_and_decimal_hour(monkeypatch: pytest.MonkeyPatch) -> None:
    client = build_client()
    monkeypatch.setattr(time_router, "datetime", FixedDateTime)

    response = client.get("/api/time/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["time_zone"] == time_router.TIME_ZONE_NAME
    # hour_decimal should include minutes/seconds rounded to 4 decimals
    assert pytest.approx(payload["hour_decimal"], rel=1e-4, abs=1e-4) == 14.7583
    assert payload["moment"] == "noon"
