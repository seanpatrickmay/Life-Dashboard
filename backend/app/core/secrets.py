"""Secrets abstraction layer for local and AWS Secrets Manager environments.

Provides:
- ``SecretsProvider`` — abstract base
- ``EnvSecretsProvider`` — reads from ``os.environ`` (local / EC2 default)
- ``SecretsManagerProvider`` — reads a JSON secret from AWS Secrets Manager
- ``get_secrets_provider()`` — factory that selects the right provider at runtime
- ``load_secrets_into_env()`` — cold-start helper for Lambda / Fargate

Import-time note: boto3 is imported lazily inside ``SecretsManagerProvider.__init__``
so importing this module has zero AWS dependency for the common local path.

Wiring at cold-start happens in ``app/aws/bootstrap.py`` (Phase 2), NOT here.
Do not import ``config.Settings`` from this module — it must remain chicken-and-egg-safe.
"""
from __future__ import annotations

import abc
import json
import os


class SecretsProvider(abc.ABC):
    """Abstract interface for retrieving application secrets."""

    @abc.abstractmethod
    def get_all(self) -> dict[str, str]:
        """Return all secrets as a flat string-to-string mapping."""
        ...


class EnvSecretsProvider(SecretsProvider):
    """Reads secrets from the process environment (local / EC2 default)."""

    def get_all(self) -> dict[str, str]:
        return dict(os.environ)


class SecretsManagerProvider(SecretsProvider):
    """Reads a single JSON secret from AWS Secrets Manager.

    Parameters
    ----------
    secret_name:
        The name or ARN of the secret (e.g. ``"life/app"``).
    client:
        An optional pre-constructed boto3 secretsmanager client. Useful for
        injecting a moto-mocked client in tests. Defaults to a fresh client
        constructed from ``AWS_REGION`` / ``AWS_ENDPOINT_URL`` env vars.
    """

    def __init__(self, secret_name: str, *, client=None) -> None:
        import boto3  # lazy import — no AWS dep when not on the SM path

        self._name = secret_name
        self._client = client or boto3.client(
            "secretsmanager",
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL") or None,
            region_name=os.environ.get("AWS_REGION") or None,
        )

    def get_all(self) -> dict[str, str]:
        resp = self._client.get_secret_value(SecretId=self._name)
        raw: str = resp.get("SecretString") or "{}"
        data: dict = json.loads(raw)
        return {str(k): str(v) for k, v in data.items()}


def get_secrets_provider() -> SecretsProvider:
    """Factory that selects a ``SecretsProvider`` based on raw env vars.

    Reads ``os.environ`` directly — never ``config.Settings`` — to stay
    chicken-and-egg-safe. The provider is selected before ``Settings()``
    is constructed.

    - ``LD_SECRETS=secretsmanager`` → ``SecretsManagerProvider`` using
      ``LD_SECRETS_NAME`` as the secret name.
    - Anything else (or unset) → ``EnvSecretsProvider``.
    """
    if os.environ.get("LD_SECRETS") == "secretsmanager":
        return SecretsManagerProvider(os.environ.get("LD_SECRETS_NAME", ""))
    return EnvSecretsProvider()


def load_secrets_into_env() -> int:
    """Cold-start helper: populate ``os.environ`` from AWS Secrets Manager.

    When ``LD_SECRETS=secretsmanager``, fetches the JSON secret named by
    ``LD_SECRETS_NAME`` and injects each key into ``os.environ`` — **only if
    that key is not already present** (env-wins / setdefault semantics).

    This allows CDK / Lambda console env vars to override individual secret
    values without changing the secret itself.

    Returns the number of keys injected (0 when no-op).

    No-op conditions (returns 0):
    - ``LD_SECRETS`` is unset or not ``"secretsmanager"``
    - ``LD_SECRETS_NAME`` is empty / unset
    """
    if os.environ.get("LD_SECRETS") != "secretsmanager":
        return 0

    name = os.environ.get("LD_SECRETS_NAME")
    if not name:
        return 0

    provider = SecretsManagerProvider(name)
    injected = 0
    for k, v in provider.get_all().items():
        if k not in os.environ:
            os.environ[k] = v
            injected += 1
    return injected
