#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/audio_output_helper.sh" ]]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/audio_output_helper.sh"
  auto_set_usb_sink || true
fi

exec "$SCRIPT_DIR/run_raspberry_pi.sh" "$@"

