
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/evaluate_parameters.py'
with open(filepath, 'r') as f:
    code = f.read()

target = """        else:
            # Value is a singular type, so nothing to evaluate
            try:
                ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
            except TypeError as e:
                print(f"\\n\\n!!! PARAMETER CRASH DETAILS !!!\\nNAME: {name}\\nVALUE: {value}\\nTYPE: {type(value)}\\n!!!\\n\\n", file=sys.stderr)
                raise e"""

replacement = """        else:
            # Value is a singular type, so nothing to evaluate
            try:
                ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
            except TypeError as e:
                import sys
                print(f"PARAM CRASH: name={name} value={value} type={type(value)}", file=sys.stderr)
                raise e"""

if target in code:
    code = code.replace(target, replacement)
    with open(filepath, 'w') as f:
        f.write(code)
    print('Fixed successfully!')
else:
    # Try the original target just in case
    orig_target = """        else:
            # Value is a singular type, so nothing to evaluate
            ensure_argument_type(value, (float, int, str, bool, bytes), 'value')"""
    if orig_target in code:
        code = code.replace(orig_target, replacement)
        with open(filepath, 'w') as f:
            f.write(code)
        print('Fixed successfully from original!')
