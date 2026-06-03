MediDroid Raspberry Pi Voice Bundle
==================================

Active Pi paths
---------------
- Main copied folder on the Pi:
  `/home/medidroid/voice sub system/raspberry_pi_bundle`
- Convenience alias on the Pi:
  `/home/medidroid/voice_sub_system/raspberry_pi_bundle`

Important note:
- `voice_sub_system/raspberry_pi_bundle` is a symlink to the real folder above.
- Use either path, but the real files live under `voice sub system`.


What this bundle contains
-------------------------
- `run_raspberry_pi.sh`
- `run_raspberry_pi_with_usb_audio.sh`
- `run_raspberry_pi_gui.sh`
- `run_mic_tester_pi.sh`
- `setup_usb_speaker_pi.sh`
- `test_usb_speaker_pi.sh`
- `install_pi_dependencies.sh`
- `audio_output_helper.sh`
- `voice_system/agent_raspberry_pi.py`
- `voice_system/control_panel_raspberry_pi.py`
- `voice_system/mic_tester_raspberry_pi.py`
- `voice_system/hospital_db.json`


Current voice-system status
---------------------------
- Wake-word mode works on Raspberry Pi 5 using the Fifine microphone.
- The Pi version now uses `arecord` for stable microphone capture.
- Audio is converted to clean `16 kHz` input before Whisper transcription.
- Navigation requests now ask the user for speed after the destination is confirmed:
  - `fastest` -> PWM `255`
  - `normal` -> PWM `170`
  - `slow` -> PWM `85`
- `stop`, `finish`, and `end` shut the voice program down cleanly.


Run commands
------------
1. Go into the folder:
   `cd "/home/medidroid/voice sub system/raspberry_pi_bundle"`

2. Make scripts executable once:
   `chmod +x run_raspberry_pi.sh run_raspberry_pi_with_usb_audio.sh run_raspberry_pi_gui.sh run_mic_tester_pi.sh setup_usb_speaker_pi.sh test_usb_speaker_pi.sh install_pi_dependencies.sh`

3. Install dependencies if needed:
   `./install_pi_dependencies.sh`

4. List microphones:
   `./run_raspberry_pi.sh --list-mics`

5. Run the live voice agent:
   `./run_raspberry_pi.sh --mic-index 0`

6. Run the GUI:
   `./run_raspberry_pi_gui.sh`

7. Run the mic tester:
   `./run_mic_tester_pi.sh`

8. Run without speaker playback:
   `./run_raspberry_pi.sh --mic-index 0 --mute`


USB speaker quick start
-----------------------
If you plug a USB speaker or USB audio dongle into the Pi:

1. Detect and select it as the default output:
   `./setup_usb_speaker_pi.sh`

2. Play a quick audio test:
   `./test_usb_speaker_pi.sh`

3. Run MediDroid with USB-audio auto-selection:
   `./run_raspberry_pi_with_usb_audio.sh --mic-index 0`


Typical live demo flow
----------------------
1. Say: `Hey MediDroid`
2. Say a destination request, for example:
   - `What departments are in this hospital?`
   - `Dr. Ahmed Al-Farsi`
   - `Cardiology`
3. After a destination is selected, the system asks:
   `What speed would you like: fastest, normal, or slow?`
4. Say one of:
   - `fastest`
   - `normal`
   - `slow`
5. The Pi prints:
   - the selected PWM target for the ESP32 side
   - the simulated ROS2 navigation goal


Movement / ESP32 notes
----------------------
- The Pi already has serial support available.
- Existing ESP32 movement scripts on the Pi use:
  - `/dev/ttyESP32` or `/dev/ttyUSB0`
  - `115200` baud
- Existing direct motor command format:
  - `M,left_pwm,right_pwm`
- Existing ROS movement bridge converts `cmd_vel` into PWM values in the `-255..255` range.

This voice bundle currently prints the selected speed profile and nav goal, so the speed choice is now part of the voice flow even before full autonomous movement integration is finished.


Speaker / amplifier status
--------------------------
Current hardware detected on the Pi:
- serial bridge to ESP32: present
- USB audio dongle: not detected
- current playback devices: HDMI only

What that means:
- The Pi can already do speech generation in software.
- The Pi does not currently have a simple analog audio output device connected.
- The PAM8403 amplifier board needs analog audio input.

If your speaker is a true single-plug USB speaker:
- plug it directly into the Pi
- do not use the PAM8403
- do not wire the speaker through the ESP32
- use the USB-speaker helper scripts in this bundle instead

Fastest working speaker path:
1. Pi 5
2. USB audio dongle (3.5 mm analog out)
3. PAM8403 input
4. speaker

Why this is the easiest path:
- the Pi bundle now includes helper scripts that auto-select a USB sink when one is plugged in
- this avoids extra ESP32 audio firmware work just to get spoken output working

For a single-plug USB speaker like a USB sound bar:
1. Pi 5
2. USB speaker directly

That is even simpler than the PAM8403 path, as long as the speaker appears in:
- `aplay -l`
- `pactl list short sinks`

ESP32-based speaker path:
- possible later, but it needs extra ESP32 audio firmware or an audio-output stage on the ESP32 side.
- that is not currently set up on this Pi.


Quick hardware checks on the Pi
-------------------------------
Check serial devices:
`ls -l /dev/ttyESP32 /dev/ttyUSB*`

Check playback devices:
`aplay -l`

Check USB devices:
`lsusb`


Known good microphone
---------------------
- Fifine USB microphone
- current working mic index on this Pi: `0`


If the program seems idle
-------------------------
- In wake-word mode, it will keep waiting until it hears a wake phrase.
- In active command mode, pauses can print `[!] Timeout`, which is normal.
- To exit cleanly, say:
  - `stop`
  - `finish`
  - `end`

