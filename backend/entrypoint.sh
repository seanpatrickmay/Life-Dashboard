#!/usr/bin/env sh
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  DB_URL="${DATABASE_URL:-}"
  SYNC_DB_URL="${DATABASE_URL_MIGRATIONS:-${DATABASE_URL_HOST:-$DB_URL}}"

  if [ -z "$DB_URL" ] && [ -z "$SYNC_DB_URL" ]; then
    echo "DATABASE_URL (async) and/or DATABASE_URL_HOST|DATABASE_URL_MIGRATIONS (sync) must be set." >&2
    exit 1
  fi

  if [ -z "$SYNC_DB_URL" ]; then
    SYNC_DB_URL="$DB_URL"
  fi
  SYNC_DB_URL=$(RAW_URL="$SYNC_DB_URL" python - <<'PY'
import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

raw = os.environ["RAW_URL"]
parsed = urlparse(raw)
scheme = parsed.scheme.replace("+asyncpg", "")
params = dict(parse_qsl(parsed.query, keep_blank_values=True))
if params.get("ssl") == "require":
    params.pop("ssl", None)
    params["sslmode"] = "require"
query = urlencode(params)
print(urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)))
PY
)

  if [ -z "$DB_URL" ]; then
    DB_URL=$(RAW_URL="$SYNC_DB_URL" python - <<'PY'
import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

raw = os.environ["RAW_URL"]
parsed = urlparse(raw)
scheme = parsed.scheme if "+asyncpg" in parsed.scheme else parsed.scheme.replace("postgresql", "postgresql+asyncpg")
params = dict(parse_qsl(parsed.query, keep_blank_values=True))
if params.get("sslmode") == "require":
    params.pop("sslmode", None)
    params["ssl"] = "require"
query = urlencode(params)
print(urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)))
PY
)
  fi

  case "$SYNC_DB_URL" in
    *"@life_db:"*|*"@localhost:"*|*"@127.0.0.1:"*)
      echo "Refusing local Postgres host in DATABASE_URL*. This deployment is configured to use Neon." >&2
      echo "Set DATABASE_URL / DATABASE_URL_HOST / DATABASE_URL_MIGRATIONS to your Neon connection strings." >&2
      exit 1
      ;;
  esac

  export DATABASE_URL="$DB_URL"
  export DATABASE_URL_MIGRATIONS="$SYNC_DB_URL"
  export DATABASE_URL_HOST="$SYNC_DB_URL"

  echo "Waiting for database..."
  python - <<'PY'
import os
import sys
import time

import psycopg2

url = os.environ["DATABASE_URL_HOST"]
for _ in range(90):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("Database ready.")
        break
    except Exception:
        time.sleep(1)
else:
    print("Database not ready after 90s.", file=sys.stderr)
    sys.exit(1)
PY

  echo "Running migrations..."
  alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
