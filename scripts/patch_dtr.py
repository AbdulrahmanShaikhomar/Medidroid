
import os

path = '/home/medidroid/ros2_ws/src/medidroid_base/medidroid_base/safety_gate.py'
with open(path, 'r') as f:
    content = f.read()

old_init = '''        try:
            self.ser = serial.Serial('/dev/ttyESP32', 115200, timeout=0.05)
            self.get_logger().info('ESP32 connected - Unified Bridge (Cmd + Odom)')
        except Exception as e:'''

new_init = '''        try:
            self.ser = serial.Serial()
            self.ser.port = '/dev/ttyESP32'
            self.ser.baudrate = 115200
            self.ser.timeout = 0.05
            self.ser.dtr = False
            self.ser.rts = False
            self.ser.open()
            self.get_logger().info('ESP32 connected - Unified Bridge (Cmd + Odom)')
        except Exception as e:'''

if old_init in content:
    content = content.replace(old_init, new_init)
    with open(path, 'w') as f:
        f.write(content)
    print("Patched DTR/RTS in safety_gate.py")
else:
    print("Could not find old_init block")
