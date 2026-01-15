#!/usr/bin/env sh
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  DB_URL="${DATABASE_URL_HOST:-$DATABASE_URL}"
  if [ -z "$DB_URL" ]; then
    echo "DATABASE_URL or DATABASE_URL_HOST must be set." >&2
    exit 1
  fi

  SYNC_DB_URL=$(printf '%s' "$DB_URL" | sed 's/+asyncpg//')
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
