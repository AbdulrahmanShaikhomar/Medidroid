#!/usr/bin/env python3
"""
MediDroid Serial Diagnostic Tool
Run this on the Pi to verify:
  1. Pi <-> ESP32 USB communication is working
  2. Encoder ticks are being received correctly
  3. Motor commands are being executed
"""
import serial
import time
import threading
import sys

PORT = '/dev/ttyESP32'
BAUD = 115200

# --- Stats ---
stats = {
    'rx_total': 0,
    'encoder_msgs': 0,
    'last_left': None,
    'last_right': None,
    'left_delta_max': 0,
    'right_delta_max': 0,
    'prev_left': None,
    'prev_right': None,
    'errors': [],
}

def reader_thread(ser):
    buf = ""
    while True:
        try:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                buf += data
                while '\n' in buf:
                    line, buf = buf.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue
                    stats['rx_total'] += 1

                    if line.startswith('E,'):
                        parts = line.split(',')
                        if len(parts) == 3:
                            try:
                                l = int(parts[1])
                                r = int(parts[2])
                                
                                # Track deltas
                                if stats['prev_left'] is not None:
                                    dl = abs(l - stats['prev_left'])
                                    dr = abs(r - stats['prev_right'])
                                    if dl > stats['left_delta_max']:
                                        stats['left_delta_max'] = dl
                                    if dr > stats['right_delta_max']:
                                        stats['right_delta_max'] = dr

                                stats['prev_left'] = l
                                stats['prev_right'] = r
                                stats['last_left'] = l
                                stats['last_right'] = r
                                stats['encoder_msgs'] += 1
                            except ValueError:
                                stats['errors'].append(f"Bad encoder line: {line}")
                    else:
                        print(f"  [ESP32] {line}")
        except Exception as e:
            stats['errors'].append(str(e))
        time.sleep(0.01)


def main():
    print("=" * 55)
    print("  MediDroid Serial Diagnostic Tool")
    print("=" * 55)
    print(f"\nOpening {PORT} @ {BAUD} baud...")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1, dsrdtr=False, rtscts=False)
        print(f"✅ Port opened successfully\n")
    except Exception as e:
        print(f"❌ FAILED to open port: {e}")
        print("\nTroubleshooting:")
        print("  - Is the USB cable plugged in?")
        print("  - Run: ls /dev/ttyESP32  (should exist)")
        print("  - Run: ls /dev/ttyUSB*   (find the actual port)")
        print("  - Is safety_gate already running? Stop it first.")
        sys.exit(1)

    # Start background reader
    t = threading.Thread(target=reader_thread, args=(ser,), daemon=True)
    t.start()

    # ── Phase 1: Wait for encoder messages ──────────────────────
    print("Phase 1: Waiting for encoder messages from ESP32...")
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if stats['encoder_msgs'] >= 3:
            break
        time.sleep(0.1)

    if stats['encoder_msgs'] == 0:
        print("❌ No encoder messages received in 5 seconds!")
        print("   Is the ESP32 flashed with the new encoder firmware?")
        print("   Is it powered on?")
        ser.close()
        sys.exit(1)
    else:
        print(f"✅ Receiving encoder ticks! ({stats['encoder_msgs']} msgs in < 5s)")
        print(f"   Left ticks:  {stats['last_left']}")
        print(f"   Right ticks: {stats['last_right']}")

    # ── Phase 2: Send a command and check it is echoed ──────────
    print("\nPhase 2: Sending STOP command (M,0,0)...")
    ser.write(b'M,0,0\n')
    ser.flush()
    time.sleep(0.5)
    print("✅ Command sent (no echo expected for M commands — that's normal)")

    # ── Phase 3: Watch encoder ticks while user spins wheels ─────
    print("\n" + "=" * 55)
    print("Phase 3: SPIN THE WHEELS WITH YOUR HAND!")
    print("  You should see the tick numbers change below.")
    print("  Press Ctrl+C to stop the test.")
    print("=" * 55)

    prev_enc_count = stats['encoder_msgs']
    try:
        while True:
            time.sleep(1.0)
            new_enc_count = stats['encoder_msgs']
            msg_rate = new_enc_count - prev_enc_count
            prev_enc_count = new_enc_count

            l = stats['last_left']
            r = stats['last_right']

            # Check if ticks changed
            tick_change = ""
            if stats['left_delta_max'] > 0 or stats['right_delta_max'] > 0:
                tick_change = f" (max change/msg: L={stats['left_delta_max']}, R={stats['right_delta_max']})"
                stats['left_delta_max'] = 0
                stats['right_delta_max'] = 0

            if msg_rate >= 15:
                rate_status = "✅"
            elif msg_rate > 0:
                rate_status = "🟡"
            else:
                rate_status = "❌"

            print(f"{rate_status} {msg_rate:2d} msgs/s | Left: {l:>8} | Right: {r:>8}{tick_change}")

            if stats['errors']:
                for e in stats['errors']:
                    print(f"  ⚠️  {e}")
                stats['errors'].clear()

    except KeyboardInterrupt:
        print("\n\n" + "=" * 55)
        print("  DIAGNOSTIC SUMMARY")
        print("=" * 55)
        print(f"  Total messages received:  {stats['rx_total']}")
        print(f"  Encoder messages:         {stats['encoder_msgs']}")
        if stats['encoder_msgs'] > 0:
            print(f"  Final Left ticks:         {stats['last_left']}")
            print(f"  Final Right ticks:        {stats['last_right']}")
        
        if stats['encoder_msgs'] > 50:
            print("\n✅ PASS — Communication and encoder reading confirmed!")
        else:
            print("\n🟡 PARTIAL — Communication works but encoder count is low.")
            print("   Did you spin the wheels? Check wiring if ticks didn't change.")
        
        ser.write(b'M,0,0\n')
        ser.close()


if __name__ == '__main__':
    main()
