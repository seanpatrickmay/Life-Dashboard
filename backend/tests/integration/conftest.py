"""Integration test conftest — requires a running LocalStack instance.

When LocalStack is unreachable the entire integration suite is skipped cleanly
so the normal unit suite (``make test``) stays green without needing Docker.

Start LocalStack with::

    make local-up

from the repo root, then run::

    cd backend && AWS_ENDPOINT_URL=http://localhost:4566 python3 -m pytest tests/integration -q
"""
from __future__ import annotations

import boto3
import pytest
import urllib.request
import urllib.error

LOCALSTACK_ENDPOINT = "http://localhost:4566"
_HEALTH_URL = f"{LOCALSTACK_ENDPOINT}/_localstack/health"


def _localstack_is_up() -> bool:
    """Return True if LocalStack is reachable and at least one service is available.

    The Community edition health endpoint returns HTTP 200 with a JSON body like
    ``{"services": {"s3": "available", ...}, "edition": "community", ...}``.
    We treat any 200 response as healthy — the service list is not authoritative
    for our purposes (services initialize lazily on first use).
    """
    try:
        with urllib.request.urlopen(_HEALTH_URL, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Session-scoped skip guard — checked once per pytest run
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Register the integration marker so -m integration works without warnings."""
    config.addinivalue_line(
        "markers",
        "integration: integration tests that require a running LocalStack instance",
    )


@pytest.fixture(scope="session", autouse=True)
def require_localstack():
    """Skip the entire integration suite when LocalStack is not available.

    Uses ``allow_module_level=True`` semantics via a session-scoped autouse
    fixture so individual tests do not need any skip decoration.
    """
    if not _localstack_is_up():
        pytest.skip(
            "LocalStack not running at http://localhost:4566 — skipping all integration tests. "
            "Run 'make local-up' from the repo root to start it.",
            allow_module_level=True,
        )


# ---------------------------------------------------------------------------
# AWS environment — dummy credentials pointing at LocalStack
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def aws_env(monkeypatch_session):
    """Inject dummy AWS credentials and endpoint for the full integration session."""
    monkeypatch_session.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch_session.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch_session.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch_session.setenv("AWS_REGION", "us-east-1")
    monkeypatch_session.setenv("AWS_ENDPOINT_URL", LOCALSTACK_ENDPOINT)
    # Ensure moto env vars do not interfere
    monkeypatch_session.delenv("AWS_SECURITY_TOKEN", raising=False)
    monkeypatch_session.delenv("AWS_SESSION_TOKEN", raising=False)


@pytest.fixture(scope="session")
def monkeypatch_session():
    """Session-scoped MonkeyPatch instance."""
    with pytest.MonkeyPatch.context() as mp:
        yield mp


# ---------------------------------------------------------------------------
# Shared boto3 client/resource fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ls_s3():
    """Session-scoped boto3 S3 client pointed at LocalStack."""
    return boto3.client(
        "s3",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )


@pytest.fixture(scope="session")
def ls_dynamodb():
    """Session-scoped boto3 DynamoDB resource pointed at LocalStack."""
    return boto3.resource(
        "dynamodb",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )


@pytest.fixture(scope="session")
def ls_dynamodb_client():
    """Session-scoped boto3 DynamoDB client pointed at LocalStack."""
    return boto3.client(
        "dynamodb",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )


@pytest.fixture(scope="session")
def ls_sqs():
    """Session-scoped boto3 SQS client pointed at LocalStack."""
    return boto3.client(
        "sqs",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )


@pytest.fixture(scope="session")
def ls_secretsmanager():
    """Session-scoped boto3 SecretsManager client pointed at LocalStack."""
    return boto3.client(
        "secretsmanager",
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
