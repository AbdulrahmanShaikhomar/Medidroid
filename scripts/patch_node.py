
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/to_parameters_list.py'
with open(filepath, 'r') as f:
    code = f.read()

# Only patch if not already patched
if "def to_parameters_list_orig(" not in code:
    new_code = code.replace("def to_parameters_list(", "def to_parameters_list_orig(")

    wrapper = """
def to_parameters_list(context, node_name, namespace, evaluated_parameters):
    try:
        with open('/home/medidroid/node_crash.log', 'a') as debug_f:
            debug_f.write(f"EVALUATING PARAMETERS FOR NODE: {node_name}\n")
        return to_parameters_list_orig(context, node_name, namespace, evaluated_parameters)
    except TypeError as e:
        with open('/home/medidroid/node_crash.log', 'a') as debug_f:
            debug_f.write(f"CRASHED ON NODE: {node_name}\n")
        raise e
"""

    with open(filepath, 'w') as f:
        f.write(new_code + wrapper)
    print('Patched to_parameters_list.py to print node names')
else:
    print('Already patched')
