"""Tests for app.core.secrets — SecretsProvider implementations.

Uses moto to mock AWS Secrets Manager so no real AWS credentials are needed.
All environment mutation is done through monkeypatch to prevent test leakage.
"""
from __future__ import annotations

import json
import os

import boto3
import pytest
from moto import mock_aws


# ---------------------------------------------------------------------------
# EnvSecretsProvider
# ---------------------------------------------------------------------------

class TestEnvSecretsProvider:
    def test_get_all_reflects_current_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """EnvSecretsProvider.get_all() must include env vars set at call time."""
        monkeypatch.setenv("_TEST_UNIQUE_KEY_XYZ", "sentinel_value_42")

        from app.core.secrets import EnvSecretsProvider

        provider = EnvSecretsProvider()
        result = provider.get_all()

        assert result["_TEST_UNIQUE_KEY_XYZ"] == "sentinel_value_42"

    def test_get_all_returns_dict_of_strings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_all() must return a plain dict with string values."""
        monkeypatch.setenv("_TEST_STR_KEY", "hello")

        from app.core.secrets import EnvSecretsProvider

        result = EnvSecretsProvider().get_all()

        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, str)


# ---------------------------------------------------------------------------
# SecretsManagerProvider
# ---------------------------------------------------------------------------

class TestSecretsManagerProvider:
    @mock_aws
    def test_get_all_returns_secret_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SecretsManagerProvider.get_all() returns the full JSON secret dict."""
        # Set up required AWS env so boto3/moto are happy
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
        monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
        monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)

        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(
            Name="life/app",
            SecretString=json.dumps({"FOO": "bar", "DATABASE_URL": "x"}),
        )

        from app.core.secrets import SecretsManagerProvider

        provider = SecretsManagerProvider("life/app", client=client)
        result = provider.get_all()

        assert result == {"FOO": "bar", "DATABASE_URL": "x"}

    @mock_aws
    def test_get_all_coerces_values_to_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SecretsManagerProvider must stringify all values (JSON may have ints, bools)."""
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
        monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
        monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)

        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(
            Name="life/coerce",
            SecretString=json.dumps({"PORT": 8080, "DEBUG": True}),
        )

        from app.core.secrets import SecretsManagerProvider

        provider = SecretsManagerProvider("life/coerce", client=client)
        result = provider.get_all()

        assert result["PORT"] == "8080"
        assert result["DEBUG"] == "True"


# ---------------------------------------------------------------------------
# load_secrets_into_env — env-wins semantics
# ---------------------------------------------------------------------------

class TestLoadSecretsIntoEnv:
    @mock_aws
    def test_injects_new_keys_and_does_not_overwrite_existing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_secrets_into_env injects secret keys absent from env, leaves present keys alone.

        This is the core env-wins / setdefault semantics proof:
        - DATABASE_URL is in the secret but NOT already in the env → injected.
        - FOO is in BOTH the secret and the env (with value "already") → NOT overwritten.
        """
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
        monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
        monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("LD_SECRETS", "secretsmanager")
        monkeypatch.setenv("LD_SECRETS_NAME", "life/app")
        # Pre-existing value that must NOT be overwritten
        monkeypatch.setenv("FOO", "already")
        # Ensure DATABASE_URL is NOT pre-set so it gets injected from the secret
        monkeypatch.delenv("DATABASE_URL", raising=False)

        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(
            Name="life/app",
            SecretString=json.dumps({"FOO": "bar", "DATABASE_URL": "x"}),
        )

        from app.core import secrets as secrets_module
        from importlib import reload
        # Reload to ensure the module reads env at call time, not import time
        reload(secrets_module)

        injected = secrets_module.load_secrets_into_env()

        # DATABASE_URL was absent → injected
        assert os.environ["DATABASE_URL"] == "x"
        # FOO was present with "already" → NOT overwritten (env wins)
        assert os.environ["FOO"] == "already"
        # Return value must be the count of NEWLY injected keys
        # (only DATABASE_URL was new; FOO was already present)
        assert injected == 1

    def test_noop_when_ld_secrets_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_secrets_into_env returns 0 and is a no-op when LD_SECRETS != secretsmanager."""
        monkeypatch.delenv("LD_SECRETS", raising=False)

        from app.core.secrets import load_secrets_into_env

        result = load_secrets_into_env()

        assert result == 0

    def test_noop_when_ld_secrets_is_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_secrets_into_env returns 0 when LD_SECRETS is explicitly 'env'."""
        monkeypatch.setenv("LD_SECRETS", "env")

        from app.core.secrets import load_secrets_into_env

        result = load_secrets_into_env()

        assert result == 0


# ---------------------------------------------------------------------------
# get_secrets_provider — factory
# ---------------------------------------------------------------------------

class TestGetSecretsProvider:
    def test_returns_env_provider_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LD_SECRETS", raising=False)

        from app.core.secrets import get_secrets_provider, EnvSecretsProvider

        provider = get_secrets_provider()

        assert isinstance(provider, EnvSecretsProvider)

    def test_returns_env_provider_when_ld_secrets_is_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LD_SECRETS", "env")

        from app.core.secrets import get_secrets_provider, EnvSecretsProvider

        provider = get_secrets_provider()

        assert isinstance(provider, EnvSecretsProvider)

    @mock_aws
    def test_returns_sm_provider_when_ld_secrets_is_secretsmanager(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LD_SECRETS", "secretsmanager")
        monkeypatch.setenv("LD_SECRETS_NAME", "life/app")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
        monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
        monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)

        from app.core.secrets import get_secrets_provider, SecretsManagerProvider

        provider = get_secrets_provider()

        assert isinstance(provider, SecretsManagerProvider)
