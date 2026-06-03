
import serial
import time

try:
    print("Opening /dev/ttyESP32 with DTR/RTS disabled...")
    ser = serial.Serial()
    ser.port = '/dev/ttyESP32'
    ser.baudrate = 115200
    ser.timeout = 1
    
    # Disable DTR/RTS so we don't reset or halt the ESP32
    ser.dtr = False
    ser.rts = False
    
    ser.open()
    time.sleep(1) # wait a moment
    
    # Read output
    print("Reading data from ESP32...")
    count = 0
    while count < 10:
        line = ser.readline().decode(errors='ignore').strip()
        if line:
            print("RECV:", line)
        count += 1
        
    print("Sending M,200,200...")
    ser.write(b'M,200,200\n')
    time.sleep(1)
    
    print("Sending M,0,0...")
    ser.write(b'M,0,0\n')
        
    ser.close()
    print("Done")
except Exception as e:
    print(f"Error: {e}")
