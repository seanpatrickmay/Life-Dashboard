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

db_url = sync_db_url
if not db_url:
    raise RuntimeError("DATABASE_URL or DATABASE_URL_HOST must be set for Alembic migrations.")

from app.db.models import entities  # noqa: F401
from app.db.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", db_url)

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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
