
import serial
import time
try:
    ser = serial.Serial('/dev/ttyESP32', 115200, timeout=2)
    ser.dtr = False
    ser.rts = False
    
    print("Reading from /dev/ttyESP32...")
    for _ in range(5):
        line = ser.readline()
        if line:
            print("ESP32:", line.decode(errors='ignore').strip())
    ser.close()
except Exception as e:
    print(f"ESP32 Error: {e}")

try:
    ser2 = serial.Serial('/dev/ttyLIDAR', 460800, timeout=2)
    print("Reading from /dev/ttyLIDAR...")
    for _ in range(5):
        line = ser2.readline()
        if line:
            print("LIDAR bytes:", len(line))
    ser2.close()
except Exception as e:
    print(f"LIDAR Error: {e}")
