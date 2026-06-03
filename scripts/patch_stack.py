
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/evaluate_parameters.py'
with open(filepath, 'r') as f:
    code = f.read()

new_line = """
    with open('/home/medidroid/node_crash.log', 'a') as debug_f:
        import traceback
        debug_f.write(f"EVALUATING PARAMETER: {name} = {value} (type: {type(value)})\n")
        debug_f.write("CALL STACK:\n")
        traceback.print_stack(file=debug_f)
    ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
"""
old_line = """
    with open('/home/medidroid/ros2_param_crash.log', 'a') as debug_f:
        debug_f.write(f"EVALUATING PARAMETER: {name} = {value} (type: {type(value)})\n")
    ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
"""

if old_line in code:
    code = code.replace(old_line, new_line)
    with open(filepath, 'w') as f:
        f.write(code)
    print('Patched evaluate_parameters.py to print stack trace')
else:
    print('Old line not found. Check if patched correctly.')
