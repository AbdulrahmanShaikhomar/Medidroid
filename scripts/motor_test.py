"""
Direct Motor Test — Send PWM directly to each wheel
Usage: python3 motor_test.py
"""
import serial
import time

ser = serial.Serial('/dev/ttyESP32', 115200, timeout=0.1)
time.sleep(1)
print("Connected to ESP32!\n")

def drive(left, right, seconds=2.5):
    """Send motor command repeatedly for given duration."""
    end = time.time() + seconds
    while time.time() < end:
        ser.write(f'M,{left},{right}\n'.encode())
        time.sleep(0.05)  # Send 20 times/second
    ser.write(b'M,0,0\n')

while True:
    print("=" * 40)
    print("  L 200      - LEFT wheels only at 200")
    print("  R 200      - RIGHT wheels only at 200")
    print("  LR 200 100 - Left=200, Right=100")
    print("  F 200      - Both forward at 200")
    print("  B 200      - Both backward at 200")
    print("  S          - Stop")
    print("  Q          - Quit")
    print("=" * 40)

    cmd = input("> ").strip().upper().split()
    if not cmd:
        continue

    if cmd[0] == 'Q':
        ser.write(b'M,0,0\n')
        break
    elif cmd[0] == 'S':
        ser.write(b'M,0,0\n')
        print("STOPPED")
    elif cmd[0] == 'F':
        spd = int(cmd[1]) if len(cmd) > 1 else 150
        print(f"FORWARD: Left={spd}, Right={spd}")
        drive(spd, spd)
        print("STOPPED")
    elif cmd[0] == 'B':
        spd = int(cmd[1]) if len(cmd) > 1 else 150
        print(f"BACKWARD: Left={-spd}, Right={-spd}")
        drive(-spd, -spd)
        print("STOPPED")
    elif cmd[0] == 'L':
        spd = int(cmd[1]) if len(cmd) > 1 else 200
        print(f"LEFT wheels={spd}, RIGHT wheels=0  (should turn RIGHT)")
        drive(spd, 0)
        print("STOPPED")
    elif cmd[0] == 'R':
        spd = int(cmd[1]) if len(cmd) > 1 else 200
        print(f"LEFT wheels=0, RIGHT wheels={spd}  (should turn LEFT)")
        drive(0, spd)
        print("STOPPED")
    elif cmd[0] == 'LR':
        l = int(cmd[1]) if len(cmd) > 1 else 150
        r = int(cmd[2]) if len(cmd) > 2 else 150
        print(f"LEFT={l}, RIGHT={r}")
        drive(l, r)
        print("STOPPED")
    else:
        print("Unknown command")

ser.close()
