
import serial
import time

ser = serial.Serial()
ser.port = '/dev/ttyESP32'
ser.baudrate = 115200
ser.timeout = 1
ser.dtr = False
ser.rts = False
ser.open()

# Don't wait for boot, just read live data
count = 0
for i in range(50):
    line = ser.readline().decode(errors='ignore').strip()
    if line.startswith('E,'):
        parts = line.split(',')
        if len(parts) >= 4:
            dist = parts[3]
            print(f"Distance: {dist} cm")
            count += 1
            if count >= 10:
                break

ser.close()
