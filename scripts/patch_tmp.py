
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/evaluate_parameters.py'
with open(filepath, 'r') as f:
    code = f.read()

# Make it completely fail-proof: write to a file in /tmp/ so we can see it!
new_line = """
    with open('/tmp/ros2_param_crash.log', 'a') as debug_f:
        debug_f.write(f"EVALUATING PARAMETER: {name} = {value} (type: {type(value)})\n")
    ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
"""
old_line = "ensure_argument_type(value, (float, int, str, bool, bytes), 'value')"
# Reset any previous patch
code = code.replace("print(f\"EVALUATING PARAMETER: {name} = {value} (type: {type(value)})\"); ensure_argument_type(value, (float, int, str, bool, bytes), 'value')", old_line)

code = code.replace(old_line, new_line)

with open(filepath, 'w') as f:
    f.write(code)
print('Patched evaluate_parameters.py to write to /tmp/')
