"""Tests for app.aws.migrate — the Fargate migration runner.

Covers:
1. Fresh DB path: create_all and stamp are called; function returns 'created+stamped'
2. Existing DB path: upgrade is called (not create_all); function returns 'upgraded'
3. Detection helper: _has_alembic_version returns True/False correctly
4. URL normalisation: async→sync, ssl→sslmode, priority order
5. Admin seed idempotency: two calls leave exactly one row

Note on SQLite and alembic commands:
    The migrations/env.py is PG-specific (version_table_schema="public",
    SET search_path).  Running alembic command.stamp or command.upgrade against
    SQLite would therefore fail.  Tests use monkeypatch to intercept those two
    calls and verify they are invoked with the correct arguments — the underlying
    Alembic command mechanics are tested by the Alembic project itself.
    Admin-seed tests create a minimal user table by hand on SQLite to avoid
    the PG-specific JSONB/ARRAY types in the production models.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_migrate() -> Any:
    """Return a freshly-imported app.aws.migrate (busts module cache)."""
    sys.modules.pop("app.aws.migrate", None)
    return importlib.import_module("app.aws.migrate")


def _create_alembic_version_table(engine: sa.engine.Engine, revision: str = "old_rev") -> None:
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)"
        ))
        conn.execute(sa.text(
            f"INSERT INTO alembic_version (version_num) VALUES ('{revision}')"
        ))


def _create_user_table(engine: sa.engine.Engine) -> None:
    """Create a minimal user table on SQLite (no PG-specific types)."""
    with engine.begin() as conn:
        conn.execute(sa.text(
            """
            CREATE TABLE IF NOT EXISTS "user" (
                id INTEGER NOT NULL PRIMARY KEY,
                email VARCHAR NOT NULL,
                display_name VARCHAR,
                role VARCHAR NOT NULL,
                email_verified BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))


# ---------------------------------------------------------------------------
# 1 & 3. Fresh DB path
# ---------------------------------------------------------------------------


def test_fresh_db_calls_create_all_and_stamp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """On a fresh DB (no alembic_version), run_migrations:
    - calls Base.metadata.create_all
    - calls command.stamp with 'head'
    - returns 'created+stamped'
    """
    db_file = tmp_path / "fresh.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", db_url)

    migrate = _reload_migrate()

    create_all_calls: list = []
    stamp_calls: list = []

    from app.db.models import Base

    def fake_create_all(bind=None, **kwargs) -> None:
        create_all_calls.append(bind)

    def fake_stamp(cfg: Config, revision: str) -> None:
        stamp_calls.append(revision)

    monkeypatch.setattr(Base.metadata, "create_all", fake_create_all)
    monkeypatch.setattr("app.aws.migrate.command.stamp", fake_stamp)

    result = migrate.run_migrations()

    assert result == "created+stamped", f"Expected 'created+stamped', got {result!r}"
    assert len(create_all_calls) == 1, "create_all should be called exactly once"
    assert len(stamp_calls) == 1, "command.stamp should be called exactly once"
    assert stamp_calls[0] == "head", f"stamp should target 'head', got {stamp_calls[0]!r}"


# ---------------------------------------------------------------------------
# 1b. Half-initialized DB guard (tables present, no alembic_version)
# ---------------------------------------------------------------------------


def test_half_initialized_db_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """run_migrations must raise RuntimeError when app tables exist but alembic_version is absent.

    This guards against silently stamping a DB that was partially set up
    outside of the migration toolchain.
    """
    db_file = tmp_path / "half_init.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", db_url)

    # Pre-create a non-alembic table to simulate a half-initialised DB
    engine = sa.create_engine(db_url, poolclass=sa.pool.NullPool)
    try:
        with engine.begin() as conn:
            conn.execute(sa.text(
                "CREATE TABLE some_app_table (id INTEGER PRIMARY KEY, name VARCHAR)"
            ))
    finally:
        engine.dispose()

    migrate = _reload_migrate()

    with pytest.raises(RuntimeError, match="alembic_version"):
        migrate.run_migrations()


# ---------------------------------------------------------------------------
# 2. Existing DB path detection
# ---------------------------------------------------------------------------


def test_has_alembic_version_true_when_table_exists(tmp_path: Path) -> None:
    """_has_alembic_version returns True when alembic_version table is present."""
    db_url = f"sqlite:///{tmp_path / 'existing.db'}"
    engine = sa.create_engine(db_url, poolclass=sa.pool.NullPool)
    try:
        _create_alembic_version_table(engine)
        migrate = _reload_migrate()
        assert migrate._has_alembic_version(engine) is True
    finally:
        engine.dispose()


def test_has_alembic_version_false_for_fresh_db(tmp_path: Path) -> None:
    """_has_alembic_version returns False when alembic_version table is absent."""
    db_url = f"sqlite:///{tmp_path / 'new.db'}"
    engine = sa.create_engine(db_url, poolclass=sa.pool.NullPool)
    try:
        migrate = _reload_migrate()
        assert migrate._has_alembic_version(engine) is False
    finally:
        engine.dispose()


def test_existing_db_calls_upgrade_not_create_all(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When alembic_version exists, run_migrations calls command.upgrade
    (not create_all) and returns 'upgraded'."""
    db_file = tmp_path / "existing.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", db_url)

    engine = sa.create_engine(db_url, poolclass=sa.pool.NullPool)
    try:
        _create_alembic_version_table(engine, revision="some_old_revision")
    finally:
        engine.dispose()

    migrate = _reload_migrate()

    upgrade_calls: list = []
    create_all_calls: list = []

    def fake_upgrade(cfg: Config, revision: str) -> None:
        upgrade_calls.append(revision)

    from app.db.models import Base

    def fake_create_all(bind=None, **kwargs) -> None:
        create_all_calls.append(1)

    monkeypatch.setattr("app.aws.migrate.command.upgrade", fake_upgrade)
    monkeypatch.setattr(Base.metadata, "create_all", fake_create_all)

    result = migrate.run_migrations()

    assert result == "upgraded", f"Expected 'upgraded', got {result!r}"
    assert len(upgrade_calls) == 1, "command.upgrade should be called exactly once"
    assert upgrade_calls[0] == "head", f"upgrade should target 'head', got {upgrade_calls[0]!r}"
    assert len(create_all_calls) == 0, "create_all must NOT be called for existing DB"


# ---------------------------------------------------------------------------
# 4. URL normalisation
# ---------------------------------------------------------------------------


def test_sync_url_already_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE_URL_MIGRATIONS with a plain sync URL passes through unchanged."""
    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", "postgresql://u:p@h/db?sslmode=require")
    monkeypatch.delenv("DATABASE_URL_HOST", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    migrate = _reload_migrate()
    assert migrate._sync_url() == "postgresql://u:p@h/db?sslmode=require"


def test_sync_url_strips_asyncpg_and_normalises_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only DATABASE_URL set with +asyncpg and ssl=require → normalised sync URL."""
    monkeypatch.delenv("DATABASE_URL_MIGRATIONS", raising=False)
    monkeypatch.delenv("DATABASE_URL_HOST", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db?ssl=require")

    migrate = _reload_migrate()
    result = migrate._sync_url()

    assert "+asyncpg" not in result, "asyncpg driver should be stripped"
    assert "ssl=require" not in result, "ssl=require should be removed"
    assert "sslmode=require" in result, "sslmode=require should be present"
    assert result.startswith("postgresql://"), "scheme should be plain postgresql"


def test_sync_url_priority_migrations_over_host_and_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE_URL_MIGRATIONS takes priority over DATABASE_URL_HOST and DATABASE_URL."""
    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", "postgresql://migrations/db")
    monkeypatch.setenv("DATABASE_URL_HOST", "postgresql://host/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app/db")

    migrate = _reload_migrate()
    assert migrate._sync_url() == "postgresql://migrations/db"


def test_sync_url_host_takes_priority_over_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE_URL_HOST takes priority over DATABASE_URL when MIGRATIONS is absent."""
    monkeypatch.delenv("DATABASE_URL_MIGRATIONS", raising=False)
    monkeypatch.setenv("DATABASE_URL_HOST", "postgresql://host/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app/db")

    migrate = _reload_migrate()
    assert migrate._sync_url() == "postgresql://host/db"


def test_sync_url_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """RuntimeError when no DB env var is set."""
    monkeypatch.delenv("DATABASE_URL_MIGRATIONS", raising=False)
    monkeypatch.delenv("DATABASE_URL_HOST", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    migrate = _reload_migrate()

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        migrate._sync_url()


# ---------------------------------------------------------------------------
# 5. Admin seed idempotency
# ---------------------------------------------------------------------------


def test_admin_seed_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """seed_admin_user() twice does not error and leaves exactly one row with correct data."""
    db_file = tmp_path / "seed.db"
    db_url = f"sqlite:///{db_file}"

    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", db_url)
    monkeypatch.setenv("ADMIN_EMAIL", "idempotent@example.com")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost")

    import app.core.config as cfg_mod
    cfg_mod.get_settings.cache_clear()

    migrate = _reload_migrate()

    # Create minimal user table (production models use PG-specific JSONB/ARRAY)
    engine = sa.create_engine(db_url, poolclass=sa.pool.NullPool)
    try:
        _create_user_table(engine)
    finally:
        engine.dispose()

    # Seed twice — neither call should raise
    migrate.seed_admin_user()
    migrate.seed_admin_user()

    engine2 = sa.create_engine(db_url, poolclass=sa.pool.NullPool)
    try:
        with engine2.connect() as conn:
            rows = conn.execute(
                sa.text('SELECT id, email, role FROM "user" WHERE id = 1')
            ).fetchall()
        assert len(rows) == 1, f"Expected exactly 1 admin row, got {len(rows)}"
        assert rows[0][1] == "idempotent@example.com"
        assert rows[0][2] == "admin"
    finally:
        engine2.dispose()
        cfg_mod.get_settings.cache_clear()


def test_admin_seed_updates_email_on_conflict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If admin row already exists with different email, seed_admin_user updates it."""
    db_file = tmp_path / "seed_update.db"
    db_url = f"sqlite:///{db_file}"

    monkeypatch.setenv("DATABASE_URL_MIGRATIONS", db_url)
    monkeypatch.setenv("ADMIN_EMAIL", "updated@example.com")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost")

    import app.core.config as cfg_mod
    cfg_mod.get_settings.cache_clear()

    migrate = _reload_migrate()

    # Pre-create the table and insert an existing row with the old email
    engine = sa.create_engine(db_url, poolclass=sa.pool.NullPool)
    try:
        _create_user_table(engine)
        with engine.begin() as conn:
            conn.execute(sa.text(
                """INSERT INTO "user" (id, email, display_name, role, email_verified)
                   VALUES (1, 'old@example.com', 'Admin', 'admin', 0)"""
            ))
    finally:
        engine.dispose()

    migrate.seed_admin_user()

    engine2 = sa.create_engine(db_url, poolclass=sa.pool.NullPool)
    try:
        with engine2.connect() as conn:
            rows = conn.execute(
                sa.text('SELECT id, email FROM "user" WHERE id = 1')
            ).fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "updated@example.com", "Email should be updated on conflict"
    finally:
        engine2.dispose()
        cfg_mod.get_settings.cache_clear()
