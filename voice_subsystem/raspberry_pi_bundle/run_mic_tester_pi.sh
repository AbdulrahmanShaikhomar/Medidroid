#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOICE_DIR="$SCRIPT_DIR/voice_system"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

cd "$VOICE_DIR"

if [ -x "$VENV_PYTHON" ]; then
  PYTHON_BIN="$VENV_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "[ERROR] Could not find python3 or python."
  exit 1
fi

exec "$PYTHON_BIN" -u mic_tester_raspberry_pi.py
