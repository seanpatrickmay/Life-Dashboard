"""Programmatic migration runner for the ECS Fargate one-shot task.

Run with:  python -m app.aws.migrate

Two-path strategy
-----------------
- FRESH DB (no alembic_version table):
    Base.metadata.create_all()  ← creates tables from current models
    alembic stamp head          ← marks DB as at head (skips broken replay chain)
- EXISTING DB (alembic_version present):
    alembic upgrade head        ← incremental migration (prod Neon path)

After schema is at head, the admin user is idempotently upserted (id=1).
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from loguru import logger

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


# ---------------------------------------------------------------------------
# URL normalisation (mirrors entrypoint.sh)
# ---------------------------------------------------------------------------


def _sync_url() -> str:
    """Resolve the sync migration URL from env, normalising async→sync.

    Priority: DATABASE_URL_MIGRATIONS > DATABASE_URL_HOST > DATABASE_URL.
    Normalisation:
      - Drop +asyncpg driver suffix from scheme
      - Convert ``ssl=require`` query param to ``sslmode=require``
    """
    raw = (
        os.environ.get("DATABASE_URL_MIGRATIONS")
        or os.environ.get("DATABASE_URL_HOST")
        or os.environ.get("DATABASE_URL")
        or ""
    )
    if not raw:
        raise RuntimeError(
            "One of DATABASE_URL_MIGRATIONS, DATABASE_URL_HOST, or DATABASE_URL must be set."
        )

    parsed = urlparse(raw)
    scheme = parsed.scheme.replace("+asyncpg", "")
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if params.get("ssl") == "require":
        params.pop("ssl", None)
        params["sslmode"] = "require"
    query = urlencode(params)
    return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))


# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------


def _alembic_config(url: str) -> Config:
    """Return an Alembic Config pointed at alembic.ini with sqlalchemy.url overridden."""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _has_alembic_version(engine: sa.engine.Engine) -> bool:
    """True if the alembic_version table exists in the DB (= tracked / existing DB)."""
    return sa.inspect(engine).has_table("alembic_version")


# ---------------------------------------------------------------------------
# Core migration logic
# ---------------------------------------------------------------------------


def run_migrations() -> str:
    """Bring the DB schema to head.

    Returns
    -------
    'upgraded'
        Existing DB — ``alembic upgrade head`` was run.
    'created+stamped'
        Fresh DB — ``Base.metadata.create_all`` was run, then stamped at head.
    """
    url = _sync_url()
    engine = sa.create_engine(url, poolclass=sa.pool.NullPool)
    cfg = _alembic_config(url)

    try:
        if _has_alembic_version(engine):
            logger.info("migrate: existing DB detected (alembic_version present) → upgrade head")
            command.upgrade(cfg, "head")
            return "upgraded"
        else:
            inspector = sa.inspect(engine)
            existing = set(inspector.get_table_names()) - {"alembic_version"}
            if existing:
                raise RuntimeError(
                    f"DB has tables {sorted(existing)!r} but no alembic_version; refusing to stamp. "
                    "Resolve migration state manually (alembic stamp) before deploying."
                )
            logger.info("migrate: fresh DB detected (no alembic_version) → create_all + stamp head")
            # Import here so all model tables are registered against Base.metadata
            from app.db.models import Base  # noqa: PLC0415

            with engine.begin() as conn:
                Base.metadata.create_all(conn)
            logger.info("migrate: create_all complete")
            command.stamp(cfg, "head")
            logger.info("migrate: stamped at head")
            return "created+stamped"
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Admin user seed
# ---------------------------------------------------------------------------


def seed_admin_user() -> None:
    """Idempotent upsert of the admin user (id=1) via the sync engine.

    Mirrors the INSERT ... ON CONFLICT logic in app/main.py _init_database().
    Reads ADMIN_EMAIL from settings so Secrets Manager injection takes effect.
    """
    from app.core.config import get_settings  # noqa: PLC0415 — lazy to respect env mutations

    admin_email = get_settings().admin_email
    url = _sync_url()
    engine = sa.create_engine(url, poolclass=sa.pool.NullPool)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO "user" (id, email, display_name, role, email_verified, created_at, updated_at)
                    VALUES (:id, :email, :name, :role, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        email = EXCLUDED.email,
                        display_name = EXCLUDED.display_name,
                        role = EXCLUDED.role,
                        email_verified = EXCLUDED.email_verified,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {"id": 1, "email": admin_email, "name": "Admin", "role": "admin"},
            )
        logger.info("migrate: admin user seeded (email={})", admin_email)
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run migrations and seed the admin user.

    When LD_SECRETS=secretsmanager, secrets are loaded from AWS Secrets Manager
    before anything else so DATABASE_URL / ADMIN_EMAIL are available.
    """
    from app.core.secrets import load_secrets_into_env  # noqa: PLC0415

    injected = load_secrets_into_env()
    if injected:
        logger.info("migrate: injected {} secret(s) from Secrets Manager", injected)

    result = run_migrations()
    seed_admin_user()
    logger.info("migrate: complete — schema={}", result)


if __name__ == "__main__":
    main()
