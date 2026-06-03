
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/evaluate_parameters.py'
with open(filepath, 'r') as f:
    code = f.read()

# Clean up all previous hacks
if 'import sys' not in code:
    code = 'import sys\n' + code

# Find the else block at line 141
target = """        else:
            # Value is a singular type, so nothing to evaluate
            ensure_argument_type(value, (float, int, str, bool, bytes), 'value')"""

replacement = """        else:
            # Value is a singular type, so nothing to evaluate
            try:
                ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
            except TypeError as e:
                print(f"\n\n!!! PARAMETER CRASH DETAILS !!!\nNAME: {name}\nVALUE: {value}\nTYPE: {type(value)}\n!!!\n\n", file=sys.stderr)
                raise e"""

if target in code:
    code = code.replace(target, replacement)
    with open(filepath, 'w') as f:
        f.write(code)
    print('Patched successfully!')
else:
    print('Target not found in code. Maybe already patched?')
