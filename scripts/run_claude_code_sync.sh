#!/bin/zsh
set -euo pipefail

ROOT="/Users/seanmay/Desktop/Current Projects/Life-Dashboard"
BACKEND_DIR="$ROOT/backend"
POETRY_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/poetry"
DEFAULT_PYTHON="/Users/seanmay/Library/Caches/pypoetry/virtualenvs/life-dashboard-backend-M5vspPLW-py3.12/bin/python"
LOCK_DIR="/tmp/life_dashboard_claude_code_sync.lock"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "$(date -Is) sync already running; exiting."
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

PYTHON_BIN="$DEFAULT_PYTHON"
if [[ -x "$POETRY_BIN" ]]; then
  cd "$BACKEND_DIR"
  VENV_PATH="$("$POETRY_BIN" env info --path 2>/dev/null || true)"
  if [[ -n "$VENV_PATH" && -x "$VENV_PATH/bin/python" ]]; then
    PYTHON_BIN="$VENV_PATH/bin/python"
  fi
fi

cd "$ROOT"
"$PYTHON_BIN" "$ROOT/scripts/sync_claude_code.py" --user-id 1 --time-zone America/New_York "$@"
