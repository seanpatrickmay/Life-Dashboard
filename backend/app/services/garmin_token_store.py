"""DB-backed encrypted Garmin token store.

Garth stores OAuth tokens as a directory of files.  In a stateless Lambda
environment there is no persistent /data directory, so we serialise the
entire directory as a tar archive, base64-encode it, encrypt it with Fernet
(reusing the audited helpers in app.core.crypto), and store a single TEXT row
per user in the garmin_token table.

Public API
----------
    await save_dir(session, user_id, token_dir)   # persist to DB
    path = await hydrate_dir(session, user_id)    # restore from DB → /tmp
    # returns None when no tokens exist for the user yet

    async with garmin_token_dir(session, user_id) as token_dir:
        # db mode: token_dir is a hydrated (or fresh empty) temp directory;
        #          on exit the directory is persisted back to DB and cleaned up.
        # dir mode: token_dir is None; GarminClient uses filesystem auto-discovery.
"""
from __future__ import annotations

import base64
import io
import shutil
import tarfile
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.models.garmin_token import GarminToken


async def save_dir(session: object, user_id: int, token_dir: str) -> None:
    """Tar the token directory, encrypt it, and upsert into garmin_token.

    Uses session.merge() for a dialect-agnostic PK-based upsert so the service
    works with both SQLite (tests) and PostgreSQL (production).
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.add(token_dir, arcname=".")
    ciphertext = encrypt_secret(base64.b64encode(buf.getvalue()).decode("ascii"))

    row = GarminToken(
        id=user_id,
        encrypted_blob=ciphertext,
        updated_at=datetime.now(timezone.utc),
    )
    await session.merge(row)  # type: ignore[union-attr]
    await session.commit()  # type: ignore[union-attr]


async def hydrate_dir(session: object, user_id: int) -> str | None:
    """Restore the token directory from DB into a fresh /tmp sub-directory.

    Returns the path to the new directory, or None if no tokens are stored.

    Security note: the tar archive is our own freshly-encrypted ciphertext
    (not user-supplied), so extractall is safe here.
    """
    row = await session.get(GarminToken, user_id)  # type: ignore[union-attr]
    if row is None:
        return None
    raw = base64.b64decode(decrypt_secret(row.encrypted_blob))
    out = tempfile.mkdtemp(prefix="garmin_tok_")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r") as tar:
        tar.extractall(out)  # noqa: S202 — archive is our own encrypted data
    return out


@asynccontextmanager
async def garmin_token_dir(session: object, user_id: int):
    """Yield a tokens directory for GarminClient.

    db mode: hydrate from DB (or a fresh temp dir if none), yield it, then
    persist the (possibly refreshed) tokens back to the DB and clean up the
    temp dir.
    dir mode (legacy): yield None so GarminClient uses its filesystem
    auto-discovery path.
    """
    if settings.ld_garmin_tokens != "db":
        yield None
        return

    token_dir = await hydrate_dir(session, user_id)
    if token_dir is None:
        token_dir = tempfile.mkdtemp(prefix="garmin_tok_")
    try:
        yield token_dir
        # persist whatever the client wrote/refreshed (idempotent re-encrypt+upsert)
        await save_dir(session, user_id, token_dir)
    finally:
        shutil.rmtree(token_dir, ignore_errors=True)
