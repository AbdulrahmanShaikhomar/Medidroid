
import serial
import time
import sys

print('Connecting to ESP32...')
try:
    ser = serial.Serial('/dev/ttyESP32', 115200, timeout=1)
    print('Connected! Listening for Encoder readings (E,Left,Right)...')
    print('Spin the wheels manually or drive the robot to see the numbers change.')
    print('Press Ctrl+C to stop.')
    while True:
        if ser.in_waiting:
            line = ser.readline().decode('utf-8').strip()
            if line.startswith('E,'):
                parts = line.split(',')
                if len(parts) == 3:
                    print(f'Left Encoder: {parts[1]:>6} | Right Encoder: {parts[2]:>6}')
        time.sleep(0.01)
except KeyboardInterrupt:
    print('\nExiting...')
except Exception as e:
    print(f'Error: {e}')
