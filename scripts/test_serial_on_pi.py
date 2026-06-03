import serial
import time

try:
    print('Opening port...')
    # Use dtr=False and rts=False to prevent resetting the ESP32!
    # If the ESP32 is powered via USB, opening the port resets it unless we disable DTR/RTS.
    ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    
    print('Waiting for ESP32...')
    start_time = time.time()
    while time.time() - start_time < 2:
        if ser.in_waiting:
            print(ser.read_all().decode('utf-8', errors='ignore'), end='')
        time.sleep(0.1)
    
    print('Sending f...')
    ser.write(b'f')
    ser.flush()
    time.sleep(0.5)
    
    response = ser.read_all().decode('utf-8', errors='ignore')
    print('Response from ESP32:', response)
    
    print('Sending s...')
    ser.write(b's')
    ser.flush()
    
    ser.close()
except Exception as e:
    print('Error:', e)
