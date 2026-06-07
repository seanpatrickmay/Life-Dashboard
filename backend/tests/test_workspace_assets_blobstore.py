"""Tests for workspace asset upload/serve via BlobStore.

Verifies that the upload path persists bytes through the BlobStore adapter,
that asset.storage_key is set correctly, and that the serve path returns the
stored bytes for the local backend.
"""
from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.db.models.workspace import WorkspaceAsset
from app.db.session import get_session
from app.routers import workspace as workspace_router
from app.storage.blob_store import LocalBlobStore


# ---------------------------------------------------------------------------
# FakeSession — minimal surface used by the asset upload/serve endpoints
# ---------------------------------------------------------------------------

class FakeSession:
    def __init__(self) -> None:
        self._store: dict[tuple[type, int], object] = {}
        self.committed = False
        self._next_id = 1

    async def get(self, model_cls: type, pk: int) -> object | None:
        return self._store.get((model_cls, pk))

    def add(self, obj: object) -> None:
        # Assign a synthetic PK if not already set
        if getattr(obj, "id", None) is None:
            obj.id = self._next_id  # type: ignore[attr-defined]
            self._next_id += 1
        self._store[(type(obj), obj.id)] = obj  # type: ignore[union-attr]

    async def commit(self) -> None:
        self.committed = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_client(session: FakeSession, blob_store: LocalBlobStore) -> TestClient:
    app = FastAPI()
    app.include_router(workspace_router.router)

    async def override_get_session():  # noqa: ANN202
        yield session

    async def override_get_current_user():  # noqa: ANN202
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_stores_bytes_via_blob_store(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upload path: bytes reach the BlobStore and storage_key is set on the asset."""
    store = LocalBlobStore(tmp_path)
    monkeypatch.setattr(workspace_router, "get_blob_store", lambda: store)

    session = FakeSession()
    # Pre-populate an asset in "pending" state (simulating the /sign step)
    asset = WorkspaceAsset(
        user_id=1,
        page_id=None,
        block_id=None,
        name="test-image.png",
        mime_type="image/png",
        size_bytes=4,
        status="pending",
    )
    asset.id = 42
    asset.storage_key = None
    session.add(asset)

    client = build_client(session, store)

    file_bytes = b"PNG!"
    response = client.put(
        "/workspace/assets/42/content",
        files={"file": ("test-image.png", BytesIO(file_bytes), "image/png")},
    )

    assert response.status_code == 204, response.text

    # asset.storage_key must be set
    assert asset.storage_key is not None
    assert asset.storage_key != ""
    assert asset.status == "uploaded"

    # bytes must be retrievable from the same store (round-trip)
    retrieved = await store.get(asset.storage_key)
    assert retrieved == file_bytes


@pytest.mark.asyncio
async def test_serve_returns_stored_bytes(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serve path: GET /assets/{id}/content returns the bytes stored in the BlobStore."""
    store = LocalBlobStore(tmp_path)
    monkeypatch.setattr(workspace_router, "get_blob_store", lambda: store)

    # Pre-store bytes
    storage_key = "42.png"
    file_bytes = b"PNG_DATA"
    await store.put(storage_key, file_bytes, content_type="image/png")

    session = FakeSession()
    asset = WorkspaceAsset(
        user_id=1,
        page_id=None,
        block_id=None,
        name="test-image.png",
        mime_type="image/png",
        size_bytes=len(file_bytes),
        status="uploaded",
    )
    asset.id = 42
    asset.storage_key = storage_key
    session.add(asset)

    client = build_client(session, store)

    response = client.get("/workspace/assets/42/content")

    assert response.status_code == 200
    assert response.content == file_bytes
    assert "image/png" in response.headers.get("content-type", "")


def test_upload_rejects_oversized_file(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upload path: files > 50 MB are rejected with 413."""
    store = LocalBlobStore(tmp_path)
    monkeypatch.setattr(workspace_router, "get_blob_store", lambda: store)

    session = FakeSession()
    asset = WorkspaceAsset(
        user_id=1,
        page_id=None,
        block_id=None,
        name="big.bin",
        mime_type="application/octet-stream",
        size_bytes=0,
        status="pending",
    )
    asset.id = 99
    asset.storage_key = None
    session.add(asset)

    client = build_client(session, store)

    big_data = b"x" * (51 * 1024 * 1024)
    response = client.put(
        "/workspace/assets/99/content",
        files={"file": ("big.bin", BytesIO(big_data), "application/octet-stream")},
    )

    assert response.status_code == 413


def test_serve_returns_404_for_missing_asset(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serve path: 404 when asset is not in the store."""
    store = LocalBlobStore(tmp_path)
    monkeypatch.setattr(workspace_router, "get_blob_store", lambda: store)

    session = FakeSession()
    # Asset exists in DB but has no bytes in the store
    asset = WorkspaceAsset(
        user_id=1,
        page_id=None,
        block_id=None,
        name="ghost.png",
        mime_type="image/png",
        size_bytes=0,
        status="uploaded",
    )
    asset.id = 77
    asset.storage_key = "77.png"  # key exists on asset but bytes never written
    session.add(asset)

    client = build_client(session, store)

    response = client.get("/workspace/assets/77/content")

    assert response.status_code == 404
