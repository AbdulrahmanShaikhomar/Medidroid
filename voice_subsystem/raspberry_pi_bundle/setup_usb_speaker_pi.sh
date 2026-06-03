#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/audio_output_helper.sh"

echo "[AUDIO] Available sinks:"
list_sinks || exit 1
echo

if auto_set_usb_sink; then
  echo "[AUDIO] Current default sink: $(show_default_sink)"
else
  echo "[AUDIO] USB speaker was not auto-selected."
  echo "[AUDIO] Plug in the USB speaker, then run this script again."
fi

