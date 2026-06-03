#!/usr/bin/env bash
# Live "when to speak" monitor for the MediDroid voice agent (no speaker needed).
echo "==================================================================="
echo " MediDroid voice monitor - watch the >>> cues to know when to talk"
echo " (Ctrl-C to stop watching; the robot/agent keep running.)"
echo "==================================================================="
tail -n 0 -f /tmp/agent.log | while IFS= read -r line; do
  printf '%s\n' "$line"
  case "$line" in
    *"WAITING FOR WAKE WORD"*) echo ">>>  SAY NOW:  hey medidroid" ;;
    *"WAKE WORD DETECTED"*)    echo ">>>  awake - command is next" ;;
    *"LISTENING"*)             echo ">>>  SPEAK NOW  (command e.g. 'take me to room C'  OR speed: fast / medium / easy)" ;;
    *"YOU:"*)                  echo ">>>  ^ that is what it heard you say" ;;
    *"LOCKED until"*)          echo ">>>  ROBOT MOVING - mic locked, do NOT speak until it returns" ;;
    *"UNLOCKED"*)              echo ">>>  back home - mic open again, you may speak" ;;
  esac
done
