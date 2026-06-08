"""Tests for Lambda cold-start bootstrap logic.

Covers:
- cold_start() idempotency (second call is a no-op)
- _validate_runtime() enforcement of LD_JOB_QUEUE=sqs when LD_RUNTIME=aws
- _validate_runtime() passes when LD_RUNTIME is unset or LD_JOB_QUEUE=sqs
"""
from __future__ import annotations

import importlib
import sys

import pytest


# ---------------------------------------------------------------------------
# Fixture: isolate the bootstrap module per test so _COLD_STARTED is reset
# ---------------------------------------------------------------------------

@pytest.fixture()
def bootstrap():
    """Import (or re-import) app.aws.bootstrap with _COLD_STARTED reset to False."""
    mod_name = "app.aws.bootstrap"
    # Remove cached module so we get a fresh import each test
    sys.modules.pop(mod_name, None)
    # Also remove the aws package cache so __init__ is re-evaluated
    sys.modules.pop("app.aws", None)

    mod = importlib.import_module(mod_name)
    mod._COLD_STARTED = False  # belt-and-suspenders reset
    yield mod

    # Cleanup after test: reset global so later imports start clean
    mod._COLD_STARTED = False
    sys.modules.pop(mod_name, None)
    sys.modules.pop("app.aws", None)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_cold_start_idempotent(bootstrap, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second call to cold_start() is a no-op — secrets and engine init run only once."""
    secrets_calls = 0
    engine_calls = 0

    def fake_load_secrets() -> int:
        nonlocal secrets_calls
        secrets_calls += 1
        return 0

    def fake_init_engine():
        nonlocal engine_calls
        engine_calls += 1

    monkeypatch.setattr(bootstrap, "load_secrets_into_env", fake_load_secrets)
    # Patch init_engine lazily (it's imported inside cold_start via local import)
    import app.db.session as session_mod
    monkeypatch.setattr(session_mod, "init_engine", fake_init_engine)

    # First call
    bootstrap.cold_start()
    assert secrets_calls == 1
    assert engine_calls == 1

    # Second call — should be no-op
    bootstrap.cold_start()
    assert secrets_calls == 1, "load_secrets_into_env should only be called once"
    assert engine_calls == 1, "init_engine should only be called once"


# ---------------------------------------------------------------------------
# _validate_runtime
# ---------------------------------------------------------------------------


def test_validate_runtime_aws_inline_raises(
    bootstrap, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LD_RUNTIME=aws with LD_JOB_QUEUE=inline must raise RuntimeError."""
    monkeypatch.setenv("LD_RUNTIME", "aws")
    monkeypatch.setenv("LD_JOB_QUEUE", "inline")

    with pytest.raises(RuntimeError, match="LD_JOB_QUEUE=sqs"):
        bootstrap._validate_runtime()


def test_validate_runtime_aws_sqs_ok(
    bootstrap, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LD_RUNTIME=aws with LD_JOB_QUEUE=sqs must not raise."""
    monkeypatch.setenv("LD_RUNTIME", "aws")
    monkeypatch.setenv("LD_JOB_QUEUE", "sqs")
    # Suppress warnings about LD_BLOB_STORE / LD_KV_STORE / LD_SECRETS
    monkeypatch.setenv("LD_BLOB_STORE", "s3")
    monkeypatch.setenv("LD_KV_STORE", "dynamodb")
    monkeypatch.setenv("LD_SECRETS", "secretsmanager")

    # Should not raise
    bootstrap._validate_runtime()


def test_validate_runtime_unset_no_raise(
    bootstrap, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When LD_RUNTIME is not set, _validate_runtime() must never raise."""
    monkeypatch.delenv("LD_RUNTIME", raising=False)
    monkeypatch.delenv("LD_JOB_QUEUE", raising=False)

    # Should not raise regardless of other settings
    bootstrap._validate_runtime()


def test_validate_runtime_local_no_raise(
    bootstrap, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LD_RUNTIME=local is not 'aws', so no validation is done."""
    monkeypatch.setenv("LD_RUNTIME", "local")
    monkeypatch.delenv("LD_JOB_QUEUE", raising=False)

    bootstrap._validate_runtime()
