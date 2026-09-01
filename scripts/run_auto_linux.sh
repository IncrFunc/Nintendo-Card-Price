#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
CONFIG="${CONFIG:-config.json}"
UI_HOST="${UI_HOST:-127.0.0.1}"
UI_PORT="${UI_PORT:-8765}"
ADB_DEVICE="${ADB_DEVICE:-}"
ADB_PATH="${ADB_PATH:-}"
ADB_OUTPUT_DIR="${ADB_OUTPUT_DIR:-}"

cd "$PROJECT_DIR"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi

args=(main.py --config "$CONFIG" auto --ui --ui-host "$UI_HOST" --ui-port "$UI_PORT")
if [[ -n "$ADB_DEVICE" ]]; then
  args+=(--device "$ADB_DEVICE")
fi
if [[ -n "$ADB_PATH" ]]; then
  args+=(--adb-path "$ADB_PATH")
fi
if [[ -n "$ADB_OUTPUT_DIR" ]]; then
  args+=(--adb-output-dir "$ADB_OUTPUT_DIR")
fi
exec "$PYTHON_BIN" "${args[@]}"
