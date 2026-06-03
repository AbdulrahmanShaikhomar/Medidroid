
import os

path = '/home/medidroid/ros2_ws/src/medidroid_base/medidroid_base/safety_gate.py'
with open(path, 'r') as f:
    content = f.read()

# Remove debug logs we added earlier
content = content.replace("                            self.get_logger().info(f'Ultrasonic: {dist_cm} cm')\n", "")
content = content.replace("                        else:\n                            self.get_logger().info(f'Invalid Parts: {line}')\n", "")
content = content.replace("        self.get_logger().info(f'Published range: {msg.range}')\n", "")

with open(path, 'w') as f:
    f.write(content)
print("Cleaned up debug logs")
