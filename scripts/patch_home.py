
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/evaluate_parameters.py'
with open(filepath, 'r') as f:
    code = f.read()

new_line = """
    with open('/home/medidroid/ros2_param_crash.log', 'a') as debug_f:
        debug_f.write(f"EVALUATING PARAMETER: {name} = {value} (type: {type(value)})\n")
    ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
"""
old_line = """
    with open('/tmp/ros2_param_crash.log', 'a') as debug_f:
        debug_f.write(f"EVALUATING PARAMETER: {name} = {value} (type: {type(value)})\n")
    ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
"""

if old_line in code:
    code = code.replace(old_line, new_line)
    with open(filepath, 'w') as f:
        f.write(code)
    print('Patched to /home/medidroid/')
else:
    print('Old line not found. Something is wrong.')
