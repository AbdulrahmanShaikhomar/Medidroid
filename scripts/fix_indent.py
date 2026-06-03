
import os
filepath = '/home/medidroid/ros2_ws/src/medidroid_base/launch/nav_launch.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "return LaunchDescription([" in line:
        new_lines.append("    return LaunchDescription([\n")
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)
