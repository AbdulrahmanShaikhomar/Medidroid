
import os

path = '/home/medidroid/ros2_ws/src/medidroid_base/medidroid_base/safety_gate.py'
with open(path, 'r') as f:
    content = f.read()

bad_line = 'pass self.get_logger().info'
good_line = 'self.get_logger().info'

if bad_line in content:
    content = content.replace(bad_line, good_line)
    with open(path, 'w') as f:
        f.write(content)
    print("Fixed syntax error in safety_gate.py")
else:
    print("Could not find syntax error")
