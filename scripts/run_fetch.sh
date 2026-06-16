#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
CONFIG="${CONFIG:-config.json}"
DRY_RUN="${DRY_RUN:-0}"

cd "$PROJECT_DIR"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

args=(main.py --config "$CONFIG" fetch)
if [[ "$DRY_RUN" == "1" || "$DRY_RUN" == "true" ]]; then
  args+=(--dry-run --no-report)
fi

exec "$PYTHON_BIN" "${args[@]}"
