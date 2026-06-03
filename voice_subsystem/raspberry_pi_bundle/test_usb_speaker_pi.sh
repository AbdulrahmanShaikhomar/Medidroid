#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/audio_output_helper.sh"

echo "[AUDIO] Available sinks:"
list_sinks || exit 1
echo

if auto_set_usb_sink; then
  echo "[AUDIO] Testing default USB sink: $(show_default_sink)"
else
  echo "[AUDIO] No USB sink detected. Testing the current default sink instead."
  echo "[AUDIO] Current default sink: $(show_default_sink)"
fi

echo
echo "[TEST] Playing ALSA sample..."
if [[ -f /usr/share/sounds/alsa/Front_Center.wav ]]; then
  if [[ "${AUDIODEV:-}" == plughw:* ]]; then
    aplay -D "$AUDIODEV" /usr/share/sounds/alsa/Front_Center.wav
  elif command -v paplay >/dev/null 2>&1; then
    paplay /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null || aplay /usr/share/sounds/alsa/Front_Center.wav
  else
    aplay /usr/share/sounds/alsa/Front_Center.wav
  fi
else
  if [[ "${AUDIODEV:-}" == plughw:* ]]; then
    speaker-test -D "$AUDIODEV" -c 1 -t sine -l 1
  else
    speaker-test -c 1 -t sine -l 1
  fi
fi

echo "[TEST] Speaker test complete."

