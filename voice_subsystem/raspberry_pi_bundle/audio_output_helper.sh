#!/usr/bin/env bash
set -euo pipefail

list_sinks() {
  if command -v pactl >/dev/null 2>&1; then
    pactl list short sinks
    return 0
  fi

  echo "[AUDIO] pactl not available, showing ALSA playback devices instead."
  aplay -l
}

find_usb_sink() {
  if command -v pactl >/dev/null 2>&1; then
    pactl list short sinks | awk '
      BEGIN { IGNORECASE=1 }
      /usb|alsa_output\..*usb/ { print $2; exit }
    '
    return 0
  fi

  python3 - <<'PY'
import re
import subprocess

result = subprocess.run(["aplay", "-l"], check=False, capture_output=True, text=True)
for line in result.stdout.splitlines():
    if "USB" not in line and "UAC" not in line:
        continue
    card_match = re.search(r"card\s+(\d+):", line)
    device_match = re.search(r"device\s+(\d+):", line)
    if card_match and device_match:
        print(f"plughw:{card_match.group(1)},{device_match.group(1)}")
        break
PY
}

set_default_sink() {
  local sink_name="$1"
  if command -v pactl >/dev/null 2>&1 && [[ "$sink_name" != plughw:* ]]; then
    pactl set-default-sink "$sink_name"
    echo "[AUDIO] Default sink set to: $sink_name"
  else
    export AUDIODEV="$sink_name"
    export ALSA_PCM_DEVICE="$sink_name"
    echo "[AUDIO] Using ALSA playback device: $sink_name"
  fi
}

auto_set_usb_sink() {
  local sink_name
  sink_name="$(find_usb_sink || true)"
  if [[ -z "${sink_name:-}" ]]; then
    echo "[AUDIO] No USB sink found. Leaving current default output unchanged."
    return 1
  fi

  set_default_sink "$sink_name"
}

show_default_sink() {
  if command -v pactl >/dev/null 2>&1; then
    pactl get-default-sink
  else
    printf '%s\n' "${AUDIODEV:-system-default}"
  fi
}

