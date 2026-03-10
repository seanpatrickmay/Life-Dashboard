from __future__ import annotations

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
import sys

from cryptography.fernet import Fernet
import pytest

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://life_dashboard:life_dashboard@localhost:5432/life_dashboard"
)
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault(
    "GARMIN_PASSWORD_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
)
os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("READINESS_ADMIN_TOKEN", "test-token")
os.environ.setdefault("GOOGLE_CLIENT_ID_LOCAL", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET_LOCAL", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI_LOCAL", "http://localhost:8000/api/auth/google/callback")

from app.core import crypto as crypto_module  # noqa: E402
from app.services import garmin_connection_service as garmin_service_module  # noqa: E402
from app.services.metrics_service import MetricsService  # noqa: E402


CURRENT_KEY = Fernet.generate_key().decode("utf-8")
LEGACY_KEY = Fernet.generate_key().decode("utf-8")


class _FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class _DummyClient:
    def __init__(self, *, tokens_dir: Path, email: str, password: str) -> None:
        self.tokens_dir = tokens_dir
        self.email = email
        self.password = password


def test_decrypt_secret_uses_fallback_key(monkeypatch: pytest.MonkeyPatch) -> None:
    encrypted = Fernet(LEGACY_KEY).encrypt(b"top-secret").decode("utf-8")
    monkeypatch.setattr(crypto_module.settings, "garmin_password_encryption_key", CURRENT_KEY)
    monkeypatch.setattr(
        crypto_module.settings, "garmin_password_encryption_key_fallbacks", LEGACY_KEY
    )

    decrypted, used_fallback = crypto_module.decrypt_secret_with_context(encrypted)

    assert decrypted == "top-secret"
    assert used_fallback is True


def test_get_client_rotates_password_when_fallback_key_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encrypted = Fernet(LEGACY_KEY).encrypt(b"hunter2").decode("utf-8")
    fake_session = _FakeSession()
    service = garmin_service_module.GarminConnectionService(fake_session)  # type: ignore[arg-type]
    connection = SimpleNamespace(
        user_id=7,
        garmin_email="runner@example.com",
        encrypted_password=encrypted,
        encryption_key_id="legacy-key",
        token_store_path="/tmp/garmin/7",
        last_sync_at=None,
        requires_reauth=False,
    )

    async def fake_get_connection(_user_id: int):  # noqa: ANN202
        return connection

    monkeypatch.setattr(service, "get_connection", fake_get_connection)
    monkeypatch.setattr(
        garmin_service_module, "GarminClient", _DummyClient
    )
    monkeypatch.setattr(crypto_module.settings, "garmin_password_encryption_key", CURRENT_KEY)
    monkeypatch.setattr(
        crypto_module.settings, "garmin_password_encryption_key_fallbacks", LEGACY_KEY
    )
    monkeypatch.setattr(
        crypto_module.settings, "garmin_password_encryption_key_id", "current-key"
    )

    client = asyncio.run(service.get_client(7))

    assert isinstance(client, _DummyClient)
    assert client.password == "hunter2"
    assert connection.encryption_key_id == "current-key"
    assert connection.encrypted_password != encrypted
    assert fake_session.commit_calls == 1


def test_metrics_ingest_marks_reauth_and_skips_invalid_stored_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, bool]] = []

    async def fake_get_connection(self, user_id: int):  # noqa: ANN001, ANN202
        return SimpleNamespace(user_id=user_id, requires_reauth=False)

    async def fake_get_client(self, user_id: int):  # noqa: ANN001, ANN202
        raise ValueError("Unable to decrypt stored credentials")

    async def fake_mark_reauth_required(  # noqa: ANN001, ANN202
        self, user_id: int, required: bool = True
    ):
        calls.append((user_id, required))

    monkeypatch.setattr(
        "app.services.metrics_service.GarminConnectionService.get_connection",
        fake_get_connection,
    )
    monkeypatch.setattr(
        "app.services.metrics_service.GarminConnectionService.get_client",
        fake_get_client,
    )
    monkeypatch.setattr(
        "app.services.metrics_service.GarminConnectionService.mark_reauth_required",
        fake_mark_reauth_required,
    )

    summary = asyncio.run(MetricsService(object()).ingest(user_id=11, lookback_days=14))

    assert summary == MetricsService._empty_summary()
    assert calls == [(11, True)]
