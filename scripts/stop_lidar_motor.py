
import serial
import time
try:
    ser = serial.Serial('/dev/ttyLIDAR', 115200, timeout=1)
    # The SLLiDAR stop command is 0xA5 0x25
    ser.write(b'\xA5\x25')
    time.sleep(0.1)
    ser.close()
    print("Stop command sent")
except Exception as e:
    print(f"Failed to send stop: {e}")
