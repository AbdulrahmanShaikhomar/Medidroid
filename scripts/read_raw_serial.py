
import serial
import time

ser = serial.Serial()
ser.port = '/dev/ttyESP32'
ser.baudrate = 115200
ser.timeout = 1
ser.dtr = False
ser.rts = False
ser.open()
time.sleep(2)

print("Reading raw serial lines from ESP32:")
for i in range(30):
    line = ser.readline().decode(errors='ignore').strip()
    if line:
        print(repr(line))
        parts = line.split(',')
        print(f"  Parts count: {len(parts)}, Parts: {parts}")

ser.close()
