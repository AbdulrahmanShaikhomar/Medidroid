
import serial
import time

try:
    print("Opening /dev/ttyESP32...")
    ser = serial.Serial('/dev/ttyESP32', 115200, timeout=1)
    time.sleep(2) # wait for reset
    
    # Read anything already there
    while ser.in_waiting:
        ser.readline()
        
    print("Sending M,200,200...")
    ser.write(b'M,200,200\n')
    time.sleep(1)
    
    print("Sending M,0,0...")
    ser.write(b'M,0,0\n')
    
    # Read output
    count = 0
    while ser.in_waiting and count < 10:
        print(ser.readline().decode(errors='ignore').strip())
        count += 1
        
    ser.close()
    print("Done")
except Exception as e:
    print(f"Error: {e}")
