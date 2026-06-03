
import os

path = '/home/medidroid/ros2_ws/src/medidroid_base/medidroid_base/safety_gate.py'
with open(path, 'r') as f:
    content = f.read()

drain_old = '''                        if len(parts) >= 4:
                            dist_cm = int(parts[3])
                            self.publish_ultrasonic(dist_cm)'''

drain_new = '''                        if len(parts) >= 4:
                            dist_cm = int(parts[3])
                            # self.get_logger().info(f'Ultrasonic: {dist_cm} cm')
                            self.publish_ultrasonic(dist_cm)
                        else:
                            pass # self.get_logger().info(f'Invalid Parts: {line}')'''

if drain_old in content:
    content = content.replace(drain_old, drain_new)

# Wait, the user said "its not reading it". Maybe safety_gate crashed?
# Let's ensure publish_ultrasonic doesn't crash
pub_old = '''        msg.range = float(dist_cm) / 100.0 # Convert to meters'''
pub_new = '''        msg.range = float(dist_cm) / 100.0 # Convert to meters
        # self.get_logger().info(f'Published range: {msg.range}')'''

if pub_old in content:
    content = content.replace(pub_old, pub_new)

# Let's actually add the logs
content = content.replace("# self.get_logger().info", "self.get_logger().info")

with open(path, 'w') as f:
    f.write(content)
print("Added debug logs to safety_gate.py")
