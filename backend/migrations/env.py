from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
import sqlalchemy as sa
from alembic import context

import os

from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

env_db_url = os.getenv("DATABASE_URL")
env_db_url_host = os.getenv("DATABASE_URL_HOST")
env_db_url_migrations = os.getenv("DATABASE_URL_MIGRATIONS")

# Prefer the explicit migrations URL when provided, then host sync URL, then app URL.
if env_db_url_migrations:
    db_url = env_db_url_migrations
else:
    db_url = env_db_url_host or env_db_url
if db_url and "+asyncpg" in db_url:
    sync_db_url = db_url.replace("+asyncpg", "")
else:
    sync_db_url = db_url

db_url = sync_db_url
if not db_url:
    raise RuntimeError("DATABASE_URL, DATABASE_URL_HOST, or DATABASE_URL_MIGRATIONS must be set for Alembic migrations.")

from app.db.models import entities  # noqa: F401
from app.db.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _build_candidates(url: str) -> list[str]:
    return [url]


target_metadata = Base.metadata

def _ensure_version_table_supports_long_ids(connection) -> None:
    """Ensure alembic_version.version_num is VARCHAR(64) on PostgreSQL.

    Alembic creates alembic_version lazily inside the first migration
    transaction, so we pre-create it here (with VARCHAR(64)) if it doesn't
    exist, and ALTER it if it does exist but is too narrow.
    """
    if connection.dialect.name != "postgresql":
        return
    result = connection.execute(
        sa.text(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_name = :table_name
              AND column_name = 'version_num'
              AND table_schema = current_schema()
            """
        ),
        {"table_name": "alembic_version"},
    ).scalar()
    if result is None:
        # Table does not exist yet — pre-create it with a wide column so that
        # Alembic's lazy creation is skipped and long revision IDs fit.
        connection.execute(sa.text(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(64) NOT NULL)"
        ))
    elif result < 64:
        connection.execute(
            sa.text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
        )

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    candidates = _build_candidates(db_url)
    last_error: Exception | None = None
    for candidate in candidates:
        config.set_main_option("sqlalchemy.url", candidate)
        try:
            connectable = engine_from_config(
                config.get_section(config.config_ini_section),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )
            with connectable.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    version_table_schema="public",
                    # Ensure the version_num column is wide enough for long revision IDs.
                    version_num_type=sa.String(64),
                )

                with context.begin_transaction():
                    if connection.dialect.name == "postgresql":
                        connection.execute(sa.text("SET search_path TO public"))
                    _ensure_version_table_supports_long_ids(connection)
                    context.run_migrations()
                return
        except Exception as exc:  # pragma: no cover - fallback handling
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No valid database URL candidate found for migrations.")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
