from __future__ import annotations

import abc
import asyncio
import functools
from pathlib import Path

from app.core.config import Settings


class BlobStore(abc.ABC):
    @abc.abstractmethod
    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None: ...

    @abc.abstractmethod
    async def get(self, key: str) -> bytes | None: ...

    @abc.abstractmethod
    async def exists(self, key: str) -> bool: ...

    async def presigned_get(self, key: str, *, expires: int = 3600) -> str | None:
        return None


class LocalBlobStore(BlobStore):
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError("invalid key (path traversal)")
        return p

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        p = self._p(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    async def get(self, key: str) -> bytes | None:
        p = self._p(key)
        return p.read_bytes() if p.exists() else None

    async def exists(self, key: str) -> bool:
        return self._p(key).exists()


class S3BlobStore(BlobStore):
    def __init__(self, bucket: str, *, client: object | None = None) -> None:
        import boto3

        self.bucket = bucket
        # Read endpoint_url from a fresh Settings() so tests can override via env
        endpoint_url = Settings().aws_endpoint_url
        self._client = client or boto3.client("s3", endpoint_url=endpoint_url)

    async def _run(self, fn, *a, **k):
        return await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(fn, *a, **k)
        )

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> None:
        kw: dict = {"Bucket": self.bucket, "Key": key, "Body": data}
        if content_type:
            kw["ContentType"] = content_type
        await self._run(self._client.put_object, **kw)

    async def get(self, key: str) -> bytes | None:
        try:
            r = await self._run(self._client.get_object, Bucket=self.bucket, Key=key)
            return r["Body"].read()
        except self._client.exceptions.NoSuchKey:
            return None

    async def exists(self, key: str) -> bool:
        try:
            await self._run(self._client.head_object, Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    async def presigned_get(self, key: str, *, expires: int = 3600) -> str | None:
        return await self._run(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )


def get_blob_store() -> BlobStore:
    # Construct a fresh Settings() at call time so that monkeypatch.setenv
    # in tests is respected — the module-level `settings` singleton is lru_cache'd
    # and would not see env changes applied after import.
    s = Settings()
    if s.ld_blob_store == "s3":
        return S3BlobStore(bucket=s.s3_asset_bucket or "")
    return LocalBlobStore(root="/tmp/life_dashboard_workspace_assets")
