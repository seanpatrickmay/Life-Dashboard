"""Shared test fixtures and environment configuration.

This conftest provides:
- Centralized environment defaults so individual test files don't need to repeat them.
- sys.path setup so ``app`` imports work when running from the repo root.

Environment values use ``setdefault`` intentionally: test files that need non-standard
values (e.g. a specific DATABASE_URL or GARMIN_PASSWORD_ENCRYPTION_KEY) can still set
their own values *before* conftest runs, or use direct assignment which takes precedence.

Note on FakeSession:
    Several test files define their own ``FakeSession`` class.  These implementations
    differ across files (varying return values, tracked methods, etc.), so they are
    intentionally NOT consolidated here.  Each file owns its own test doubles.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path: ensure the backend package root is importable
# ---------------------------------------------------------------------------
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# ---------------------------------------------------------------------------
# Environment defaults — safe for the majority of unit tests
# ---------------------------------------------------------------------------
_ENV_DEFAULTS: dict[str, str] = {
    "DATABASE_URL": "sqlite+aiosqlite:///test.db",
    "ADMIN_EMAIL": "test@example.com",
    "FRONTEND_URL": "http://localhost:4173",
    "GARMIN_PASSWORD_ENCRYPTION_KEY": "test-key",
    "OPENAI_API_KEY": "test-openai-key",
    "READINESS_ADMIN_TOKEN": "test-token",
}

for key, value in _ENV_DEFAULTS.items():
    os.environ.setdefault(key, value)
