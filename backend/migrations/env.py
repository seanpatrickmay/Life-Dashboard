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

db_url = os.getenv("DATABASE_URL_HOST") or os.getenv("DATABASE_URL")
if db_url and "+asyncpg" in db_url:
    sync_db_url = db_url.replace("+asyncpg", "")
else:
    sync_db_url = db_url


def _rewrite_localhost_if_in_container(url: str | None) -> str | None:
    if not url:
        return url
    # If running inside docker-compose, localhost will not reach the db service. Rewrite to 'db'.
    if os.path.exists("/.dockerenv") and ("localhost" in url or "127.0.0.1" in url):
        return url.replace("localhost", "db").replace("127.0.0.1", "db")
    return url


db_url = _rewrite_localhost_if_in_container(sync_db_url)
if not db_url:
    raise RuntimeError("DATABASE_URL or DATABASE_URL_HOST must be set for Alembic migrations.")

from app.db.models import entities  # noqa: F401
from app.db.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _build_candidates(url: str) -> list[str]:
    # If we're inside a container, allow 'db' rewrite. Host runs should stick to the provided URL.
    if not os.path.exists("/.dockerenv"):
        return [url]

    candidates: list[str] = []
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        if parsed.hostname:
            hosts = [parsed.hostname]
            if parsed.hostname in ("localhost", "127.0.0.1"):
                hosts.append("db")
            if parsed.hostname == "db":
                hosts.extend(["localhost", "127.0.0.1"])

            seen: set[str] = set()

            def build_url(host: str) -> str:
                netloc = ""
                if parsed.username:
                    netloc += parsed.username
                    if parsed.password:
                        netloc += f":{parsed.password}"
                    netloc += "@"
                netloc += host
                if parsed.port:
                    netloc += f":{parsed.port}"
                return urlunparse(
                    (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
                )

            for host in hosts:
                rebuilt = build_url(host)
                if rebuilt not in seen:
                    seen.add(rebuilt)
                    candidates.append(rebuilt)
        else:
            candidates = [url]
    except Exception:
        candidates = [url]

    return candidates


target_metadata = Base.metadata

def _ensure_version_table_supports_long_ids(connection) -> None:
    """Bump alembic_version.version_num length so long revision IDs do not fail."""
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
    if result is not None and result < 64:
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
                _ensure_version_table_supports_long_ids(connection)
                context.configure(connection=connection, target_metadata=target_metadata)

                with context.begin_transaction():
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
