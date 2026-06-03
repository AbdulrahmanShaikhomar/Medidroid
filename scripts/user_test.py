import serial, time
try:
    s = serial.Serial('/dev/ttyUSB1', 115200, timeout=1)
    s.setDTR(False)
    s.setRTS(False)
    time.sleep(2)  
    print("Sending SPEED 150")
    s.write(b"150\n")
    time.sleep(0.5)
    print("Sending FORWARD for 5 seconds")
    s.write(b"F\n")
    time.sleep(5)
    print("Sending STOP")
    s.write(b"S\n")
    s.close()
    print("DONE")
except Exception as e:
    print(f"FAILED: {e}")
