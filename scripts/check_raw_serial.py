
import serial
import time

try:
    ser = serial.Serial('/dev/ttyESP32', 115200, timeout=1)
    print('Reading raw serial data. If you see nothing, the ESP32 is silent.')
    while True:
        if ser.in_waiting:
            raw_bytes = ser.readline()
            try:
                print('RAW:', raw_bytes.decode('utf-8').strip())
            except:
                print('GARBLED BYTES:', raw_bytes)
        else:
            time.sleep(0.01)
except KeyboardInterrupt:
    pass
