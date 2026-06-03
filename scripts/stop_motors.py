import serial
import time
try:
    s = serial.Serial('/dev/ttyUSB2', 115200, timeout=1)
    s.setDTR(False)
    s.setRTS(False)
    time.sleep(2)
    s.write(b"S\n")
    s.close()
    print("Sent stop command to /dev/ttyUSB2")
except Exception as e:
    print(f"Failed to open /dev/ttyUSB2: {e}")
    try:
        s = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
        s.setDTR(False)
        s.setRTS(False)
        time.sleep(2)
        s.write(b"S\n")
        s.close()
        print("Sent stop command to /dev/ttyUSB0")
    except Exception as e2:
        print(f"Failed to open /dev/ttyUSB0: {e2}")
