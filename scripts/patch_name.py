
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/evaluate_parameters.py'
with open(filepath, 'r') as f:
    code = f.read()

target = """        else:
            # Value is a singular type, so nothing to evaluate
            try:
                ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
            except TypeError as e:
                import sys
                print(f"PARAM CRASH: name={name} value={value} type={type(value)}", file=sys.stderr)
                raise e"""

replacement = """        else:
            # Value is a singular type, so nothing to evaluate
            try:
                ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
            except TypeError as e:
                import sys
                try:
                    name_str = name[0].text
                except:
                    name_str = str(name)
                print(f"PARAM CRASH: name={name_str} value={value} type={type(value)}", file=sys.stderr)
                raise e"""

if target in code:
    code = code.replace(target, replacement)
    with open(filepath, 'w') as f:
        f.write(code)
    print('Patched successfully!')
else:
    print('Target not found')
