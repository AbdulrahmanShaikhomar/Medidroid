import serial
import time

s = serial.Serial("/dev/ttyESP32", 115200, timeout=0.1)
time.sleep(0.2)

NL = bytes([10])
fwd = b"M,150,150" + NL
s.write(fwd)
print("Sent M,150,150")
time.sleep(1.5)

stop = b"M,0,0" + NL
s.write(stop)
print("Sent stop")
time.sleep(0.2)

while s.in_waiting:
    line = s.readline().decode().strip()
    print("ESP32:", line)

s.close()
print("Done")
