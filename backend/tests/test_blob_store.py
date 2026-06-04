import pytest
from app.storage.blob_store import LocalBlobStore, get_blob_store

@pytest.mark.asyncio
async def test_local_put_get_roundtrip(tmp_path):
    store = LocalBlobStore(root=tmp_path)
    await store.put("a/b.bin", b"hello", content_type="application/octet-stream")
    assert await store.get("a/b.bin") == b"hello"
    assert await store.exists("a/b.bin") is True

@pytest.mark.asyncio
async def test_local_missing_returns_none(tmp_path):
    store = LocalBlobStore(root=tmp_path)
    assert await store.get("nope") is None
    assert await store.exists("nope") is False

@pytest.mark.asyncio
async def test_local_rejects_path_traversal(tmp_path):
    store = LocalBlobStore(root=tmp_path)
    with pytest.raises(ValueError):
        await store.put("../escape.bin", b"x")


@pytest.mark.asyncio
async def test_local_rejects_sibling_prefix_traversal(tmp_path):
    """A sibling dir with a matching prefix must be rejected.

    The old str.startswith check had a bug: given root=/tmp/life_dashboard_workspace_assets,
    a key like '../life_dashboard_workspace_assets_evil/x' would produce a resolved path
    starting with '/tmp/life_dashboard_workspace_assets' (the prefix matches), so it would
    pass the old guard and escape the root.  Path.is_relative_to() correctly rejects it.
    """
    # Simulate the real production root name to exercise the prefix-collision case.
    root = tmp_path / "life_dashboard_workspace_assets"
    root.mkdir()
    store = LocalBlobStore(root=root)
    with pytest.raises(ValueError, match="path traversal"):
        await store.put("../life_dashboard_workspace_assets_evil/x", b"x")

def test_factory_defaults_to_local(monkeypatch):
    monkeypatch.setenv("LD_BLOB_STORE", "local")
    assert get_blob_store().__class__.__name__ == "LocalBlobStore"

def test_factory_s3_when_selected(monkeypatch):
    monkeypatch.setenv("LD_BLOB_STORE", "s3")
    monkeypatch.setenv("LD_S3_ASSET_BUCKET", "b")
    assert get_blob_store().__class__.__name__ == "S3BlobStore"
