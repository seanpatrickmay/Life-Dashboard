#!/bin/zsh
set -euo pipefail

ROOT="/Users/seanmay/Desktop/Current Projects/Life-Dashboard"
BACKEND_DIR="$ROOT/backend"
POETRY_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/poetry"
DEFAULT_PYTHON="/Users/seanmay/Library/Caches/pypoetry/virtualenvs/life-dashboard-backend-M5vspPLW-py3.12/bin/python"

PYTHON_BIN="$DEFAULT_PYTHON"
if [[ -x "$POETRY_BIN" ]]; then
  cd "$BACKEND_DIR"
  VENV_PATH="$("$POETRY_BIN" env info --path 2>/dev/null || true)"
  if [[ -n "$VENV_PATH" && -x "$VENV_PATH/bin/python" ]]; then
    PYTHON_BIN="$VENV_PATH/bin/python"
  fi
fi

cd "$ROOT"
"$PYTHON_BIN" "$ROOT/scripts/replay_imessage_processing_dry_run.py" "$@"
