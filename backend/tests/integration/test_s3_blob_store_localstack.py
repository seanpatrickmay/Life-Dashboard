"""Integration tests for S3BlobStore against real LocalStack.

Proves:
- put / get round-trip returns the original bytes
- exists() returns True for present keys, False for absent ones
- presigned_get() returns a non-empty string URL containing the bucket name

LocalStack must be running (make local-up).  Tests are skipped automatically
when LocalStack is unreachable (see conftest.py).
"""
from __future__ import annotations

import pytest

BUCKET = "integ-test-blob-store"


@pytest.fixture(scope="module")
def s3_bucket(ls_s3):
    """Create (and clean up) a dedicated S3 bucket for this module's tests."""
    ls_s3.create_bucket(Bucket=BUCKET)
    yield BUCKET
    # Best-effort cleanup: delete all objects then the bucket
    try:
        paginator = ls_s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BUCKET):
            for obj in page.get("Contents", []):
                ls_s3.delete_object(Bucket=BUCKET, Key=obj["Key"])
        ls_s3.delete_bucket(Bucket=BUCKET)
    except Exception:
        pass


@pytest.fixture()
def store(s3_bucket):
    """Construct S3BlobStore using the LocalStack bucket.

    AWS_ENDPOINT_URL is already in the environment (set by the session-scoped
    aws_env fixture in conftest.py), so S3BlobStore() picks it up via
    Settings().aws_endpoint_url as intended.
    """
    from app.storage.blob_store import S3BlobStore

    return S3BlobStore(s3_bucket)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_get_roundtrip(store):
    """Bytes stored via put() are returned unchanged by get()."""
    data = b"hello localstack s3 \x00\xff"
    await store.put("integ/test.bin", data)
    result = await store.get("integ/test.bin")
    assert result == data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_put_get_with_content_type(store):
    """put() with an explicit content_type succeeds; get() returns the same bytes."""
    data = b'{"ok": true}'
    await store.put("integ/test.json", data, content_type="application/json")
    result = await store.get("integ/test.json")
    assert result == data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_missing_returns_none(store):
    """get() on a non-existent key returns None (does not raise)."""
    result = await store.get("integ/does-not-exist.bin")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exists_true_after_put(store):
    """exists() returns True after a key has been put."""
    await store.put("integ/exists-check.bin", b"data")
    assert await store.exists("integ/exists-check.bin") is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exists_false_for_missing_key(store):
    """exists() returns False for a key that has never been put."""
    assert await store.exists("integ/never-written.bin") is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_presigned_get_is_nonempty_string_with_bucket(store):
    """presigned_get() returns a non-empty URL string that references the bucket."""
    await store.put("integ/presign.bin", b"presign me")
    url = await store.presigned_get("integ/presign.bin", expires=60)
    assert isinstance(url, str)
    assert len(url) > 0
    # LocalStack presigned URLs contain the bucket name
    assert BUCKET in url
