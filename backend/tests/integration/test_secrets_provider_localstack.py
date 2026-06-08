"""Integration tests for SecretsManagerProvider against real LocalStack.

Proves:
- get_all() returns the full JSON secret as a dict
- load_secrets_into_env() injects missing keys into os.environ
- load_secrets_into_env() does NOT overwrite keys that are already in os.environ
  (env-wins / setdefault semantics)

LocalStack must be running (make local-up).  Tests are skipped automatically
when LocalStack is unreachable (see conftest.py).
"""
from __future__ import annotations

import json
import os

import pytest

SECRET_NAME = "integ/test-secret"


@pytest.fixture(scope="module")
def test_secret(ls_secretsmanager):
    """Create (and clean up) a Secrets Manager secret for this module's tests."""
    secret_value = json.dumps({
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "API_KEY": "secret-api-key",
    })
    ls_secretsmanager.create_secret(
        Name=SECRET_NAME,
        SecretString=secret_value,
    )
    yield SECRET_NAME
    # Best-effort cleanup
    try:
        ls_secretsmanager.delete_secret(
            SecretId=SECRET_NAME,
            ForceDeleteWithoutRecovery=True,
        )
    except Exception:
        pass


@pytest.mark.integration
def test_get_all_returns_secret_dict(ls_secretsmanager, test_secret):
    """SecretsManagerProvider.get_all() returns the full JSON secret as a flat dict."""
    from app.core.secrets import SecretsManagerProvider

    provider = SecretsManagerProvider(SECRET_NAME, client=ls_secretsmanager)
    result = provider.get_all()

    assert result == {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "API_KEY": "secret-api-key",
    }


@pytest.mark.integration
def test_get_all_returns_string_values(ls_secretsmanager, test_secret):
    """All values returned by get_all() are strings (int/bool JSON types coerced)."""
    # Create a separate secret with mixed types
    mixed_name = "integ/mixed-types"
    ls_secretsmanager.create_secret(
        Name=mixed_name,
        SecretString=json.dumps({"PORT": 8080, "DEBUG": True, "NAME": "app"}),
    )
    try:
        from app.core.secrets import SecretsManagerProvider

        provider = SecretsManagerProvider(mixed_name, client=ls_secretsmanager)
        result = provider.get_all()

        assert result["PORT"] == "8080"
        assert result["DEBUG"] == "True"
        assert result["NAME"] == "app"
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, str)
    finally:
        try:
            ls_secretsmanager.delete_secret(
                SecretId=mixed_name,
                ForceDeleteWithoutRecovery=True,
            )
        except Exception:
            pass


@pytest.mark.integration
def test_load_secrets_injects_missing_keys(monkeypatch, test_secret):
    """load_secrets_into_env() injects secret keys absent from os.environ."""
    monkeypatch.setenv("LD_SECRETS", "secretsmanager")
    monkeypatch.setenv("LD_SECRETS_NAME", SECRET_NAME)
    # Ensure the secret keys are NOT already in the environment
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    from app.core.secrets import load_secrets_into_env

    injected = load_secrets_into_env()

    assert os.environ.get("DB_HOST") == "localhost"
    assert os.environ.get("DB_PORT") == "5432"
    assert os.environ.get("API_KEY") == "secret-api-key"
    assert injected == 3


@pytest.mark.integration
def test_load_secrets_does_not_overwrite_existing_keys(monkeypatch, test_secret):
    """load_secrets_into_env() must not overwrite pre-existing env keys (env-wins)."""
    monkeypatch.setenv("LD_SECRETS", "secretsmanager")
    monkeypatch.setenv("LD_SECRETS_NAME", SECRET_NAME)
    # Pre-set DB_HOST — must NOT be overwritten
    monkeypatch.setenv("DB_HOST", "already-set")
    monkeypatch.delenv("DB_PORT", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    from app.core.secrets import load_secrets_into_env

    injected = load_secrets_into_env()

    # DB_HOST was already present — env wins
    assert os.environ["DB_HOST"] == "already-set"
    # Other keys were absent — injected
    assert os.environ.get("DB_PORT") == "5432"
    assert os.environ.get("API_KEY") == "secret-api-key"
    # Only 2 keys were new
    assert injected == 2


@pytest.mark.integration
def test_load_secrets_noop_when_ld_secrets_unset(monkeypatch):
    """load_secrets_into_env() is a no-op when LD_SECRETS is not 'secretsmanager'."""
    monkeypatch.delenv("LD_SECRETS", raising=False)

    from app.core.secrets import load_secrets_into_env

    result = load_secrets_into_env()
    assert result == 0
