
import serial
import time

try:
    print("Opening /dev/ttyUSB0...")
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    time.sleep(2) # wait for reset
    
    print("Sending M,200,200...")
    ser.write(b'M,200,200\n')
    time.sleep(1)
    
    print("Sending s (stop)...")
    ser.write(b's\n')
    time.sleep(1)
    
    print("Sending M,0,0...")
    ser.write(b'M,0,0\n')
    
    # Read output
    while ser.in_waiting:
        print(ser.readline().decode(errors='ignore').strip())
        
    ser.close()
    print("Done")
except Exception as e:
    print(f"Error: {e}")
