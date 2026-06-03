
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/evaluate_parameters.py'
with open(filepath, 'r') as f:
    code = f.read()

if 'print(f"EVALUATING PARAMETER' not in code:
    old_line = "ensure_argument_type(value, (float, int, str, bool, bytes), 'value')"
    new_line = "print(f\"EVALUATING PARAMETER: {name} = {value} (type: {type(value)})\"); " + old_line
    code = code.replace(old_line, new_line)
    
    with open(filepath, 'w') as f:
        f.write(code)
    print('Patched evaluate_parameters.py')
else:
    print('Already patched.')
