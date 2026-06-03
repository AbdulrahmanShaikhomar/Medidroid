
import os

path = '/home/medidroid/ros2_ws/src/medidroid_base/medidroid_base/safety_gate.py'
with open(path, 'r') as f:
    content = f.read()

# 1. Add Range import
if 'from sensor_msgs.msg import Range' not in content:
    content = content.replace('from nav_msgs.msg import Odometry', 'from nav_msgs.msg import Odometry\nfrom sensor_msgs.msg import Range')

# 2. Add publisher in __init__
init_old = "self.odom_pub = self.create_publisher(Odometry, 'odom', 10)"
init_new = "self.odom_pub = self.create_publisher(Odometry, 'odom', 10)\n        self.ultra_pub = self.create_publisher(Range, 'ultrasonic', 10)"
if 'self.ultra_pub =' not in content:
    content = content.replace(init_old, init_new)

# 3. Add distance parsing in _drain_serial
drain_old = '''                        if len(parts) == 3:
                            ticks_L = int(parts[1])
                            ticks_R = int(parts[2])
                            self.update_odometry(ticks_L, ticks_R)'''
drain_new = '''                        if len(parts) >= 3:
                            ticks_L = int(parts[1])
                            ticks_R = int(parts[2])
                            self.update_odometry(ticks_L, ticks_R)
                        if len(parts) >= 4:
                            dist_cm = int(parts[3])
                            self.publish_ultrasonic(dist_cm)'''
if 'self.publish_ultrasonic' not in content:
    content = content.replace(drain_old, drain_new)

# 4. Add publish_ultrasonic method
publish_method = '''
    def publish_ultrasonic(self, dist_cm):
        if dist_cm < 0:
            return # invalid reading
        
        msg = Range()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'ultrasonic_link'
        msg.radiation_type = Range.ULTRASOUND
        msg.field_of_view = 0.52 # ~30 degrees
        msg.min_range = 0.02 # 2cm
        msg.max_range = 4.00 # 400cm
        msg.range = float(dist_cm) / 100.0 # Convert to meters
        
        self.ultra_pub.publish(msg)
'''
if 'def publish_ultrasonic' not in content:
    content = content.replace('def cmd_callback(self, msg):', publish_method + '\n    def cmd_callback(self, msg):')

with open(path, 'w') as f:
    f.write(content)
print("Patched safety_gate.py with ultrasonic logic")
