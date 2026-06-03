import serial
import time

try:
    s = serial.Serial('/dev/ttyUSB1', 115200, timeout=1)
    s.setDTR(False)
    s.setRTS(False)
    time.sleep(2)  
    print("Flushing buffer...")
    s.reset_input_buffer()
    
    print("1. Sending STOP command...")
    s.write(b"S\n")
    time.sleep(1)
    
    print("2. Sending SPEED 50 command...")
    s.write(b"50\n")
    time.sleep(1)
    
    print("3. Sending FORWARD command (danger)...")
    s.write(b"F\n")
    time.sleep(2)
    
    print("4. Done. Sending STOP command...")
    s.write(b"S\n")
    s.close()
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
