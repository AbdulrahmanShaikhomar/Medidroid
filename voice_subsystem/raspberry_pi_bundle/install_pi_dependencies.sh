#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "[1/3] Updating apt package lists..."
sudo apt update

echo "[2/3] Installing system packages..."
sudo apt install -y ffmpeg mpg123 portaudio19-dev python3-pyaudio python3-tk python3-pip python3-venv alsa-utils pulseaudio-utils

echo "[3/3] Creating virtual environment and installing Python packages..."
python3 -m venv "$VENV_DIR"

"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel setuptools
"$VENV_DIR/bin/python" -m pip install speechrecognition edge-tts faster-whisper pyaudio

echo
echo "[DONE] Raspberry Pi dependencies installed in $VENV_DIR."

