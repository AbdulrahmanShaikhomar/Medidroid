
import os
filepath = '/home/medidroid/ros2_ws/src/medidroid_base/launch/nav_launch.py'
with open(filepath, 'r') as f:
    code = f.read()

if 'SetRemap' not in code:
    code = code.replace('from launch_ros.actions import Node', 'from launch_ros.actions import Node, SetRemap')
    
    remap_str = """
    remap_cmd_vel = SetRemap(src='cmd_vel_smoothed', dst='cmd_vel')
    """
    code = code.replace('return LaunchDescription([', remap_str + '    return LaunchDescription([\n        remap_cmd_vel,')

    with open(filepath, 'w') as f:
        f.write(code)
    print('Patched nav_launch.py!')
else:
    print('Already patched!')
