#!/usr/bin/env python3
import struct
import os
import time
import serial
import subprocess

TARGET_NAME = "LinTx LinTx Keyboard"

def find_button_device():
    # Parse /proc/bus/input/devices to find the event number for our keyboard
    try:
        with open("/proc/bus/input/devices", "r") as f:
            lines = f.readlines()
            
        found_target = False
        for line in lines:
            if TARGET_NAME in line:
                found_target = True
            if found_target and line.startswith("H: Handlers="):
                # e.g., H: Handlers=sysrq kbd event1 leds
                parts = line.strip().split()
                for part in parts:
                    if part.startswith("event"):
                        return "/dev/input/" + part
    except Exception as e:
        print("Error reading devices:", e)
    return None

def trigger_estop():
    print("EMERGENCY STOP TRIGGERED!")
    
    # 1. Hardware Kill
    try:
        ser = serial.Serial()
        ser.port = '/dev/ttyESP32'
        ser.baudrate = 115200
        ser.timeout = 0.1
        ser.dtr = False
        ser.rts = False
        ser.open()
        ser.write(b'M,0,0\n')
        ser.close()
        print("Hardware motor stop sent to ESP32.")
    except Exception as e:
        print(f"Failed to send hardware stop: {e}")

    # 2. Software Kill
    try:
        subprocess.run(['pkill', '-9', '-f', 'ros2'])
        print("Terminated ROS 2 processes.")
    except Exception as e:
        print(f"Failed to kill ROS: {e}")

def main():
    dev_path = None
    while not dev_path:
        dev_path = find_button_device()
        if not dev_path:
            print(f"Waiting for {TARGET_NAME}...")
            time.sleep(2)
            
    print(f"Listening on {dev_path}")
    
    # Grab the device so normal keyboard inputs are ignored
    # EVIOCGRAB is _IOW('E', 0x90, int) -> 0x40044590
    import fcntl
    
    try:
        fd = os.open(dev_path, os.O_RDONLY)
        try:
            fcntl.ioctl(fd, 0x40044590, 1) # Grab
        except Exception as e:
            print("Could not grab device:", e)
            
        # struct input_event is 24 bytes on 64-bit linux
        # struct timeval (16 bytes), type (2), code (2), value (4)
        EVENT_SIZE = 24
        
        while True:
            data = os.read(fd, EVENT_SIZE)
            if len(data) == EVENT_SIZE:
                # unpack 'llHHi' -> long long sec, long long usec, unsigned short type, unsigned short code, int value
                sec, usec, type_, code, value = struct.unpack('llHHi', data)
                
                # EV_KEY is 1, value 1 is down, value 2 is repeat
                if type_ == 1 and value in [1, 2]:
                    trigger_estop()
                    time.sleep(1) # debounce
    except KeyboardInterrupt:
        pass
    finally:
        try:
            fcntl.ioctl(fd, 0x40044590, 0) # Ungrab
            os.close(fd)
        except:
            pass

if __name__ == '__main__':
    main()
