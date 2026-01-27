#!/usr/bin/env sh
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  DB_URL="${DATABASE_URL:-$DATABASE_URL_HOST}"
  if [ -z "$DB_URL" ]; then
    if [ -n "${POSTGRES_USER:-}" ] && [ -n "${POSTGRES_PASSWORD:-}" ] && [ -n "${POSTGRES_DB:-}" ]; then
      DB_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432}/${POSTGRES_DB}"
    fi
  fi

  if [ -z "$DB_URL" ]; then
    echo "DATABASE_URL, DATABASE_URL_HOST, or POSTGRES_* must be set." >&2
    exit 1
  fi

  if [ -f "/.dockerenv" ]; then
    TARGET_HOST="${POSTGRES_HOST:-life_db}"
    if [ "$TARGET_HOST" = "localhost" ] || [ "$TARGET_HOST" = "127.0.0.1" ]; then
      TARGET_HOST="life_db"
    fi
    DB_URL=$(printf '%s' "$DB_URL" \
      | sed "s@localhost@${TARGET_HOST}@g" \
      | sed "s@127\\.0\\.0\\.1@${TARGET_HOST}@g" \
      | sed "s@//db@//${TARGET_HOST}@g" \
      | sed "s@//life-db@//${TARGET_HOST}@g" \
      | sed "s@//life_db@//${TARGET_HOST}@g")
  fi

  export DATABASE_URL="$DB_URL"
  MIGRATIONS_URL="${DATABASE_URL_MIGRATIONS:-$DB_URL}"
  if [ -f "/.dockerenv" ]; then
    TARGET_HOST="${POSTGRES_HOST:-life_db}"
    if [ "$TARGET_HOST" = "localhost" ] || [ "$TARGET_HOST" = "127.0.0.1" ]; then
      TARGET_HOST="life_db"
    fi
    MIGRATIONS_URL=$(printf '%s' "$MIGRATIONS_URL" \
      | sed "s@localhost@${TARGET_HOST}@g" \
      | sed "s@127\\.0\\.0\\.1@${TARGET_HOST}@g" \
      | sed "s@//db@//${TARGET_HOST}@g" \
      | sed "s@//life-db@//${TARGET_HOST}@g" \
      | sed "s@//life_db@//${TARGET_HOST}@g")
  fi

  SYNC_DB_URL=$(printf '%s' "$MIGRATIONS_URL" | sed 's/+asyncpg//')
  export DATABASE_URL_MIGRATIONS="$SYNC_DB_URL"
  export DATABASE_URL_HOST="$SYNC_DB_URL"

  echo "Waiting for database..."
  python - <<'PY'
import os
import sys
import time

import psycopg2

url = os.environ["DATABASE_URL_HOST"]
for _ in range(30):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("Database ready.")
        break
    except Exception:
        time.sleep(1)
else:
    print("Database not ready after 30s.", file=sys.stderr)
    sys.exit(1)
PY

  echo "Running migrations..."
  alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
