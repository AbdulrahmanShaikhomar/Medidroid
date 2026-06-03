
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/to_parameters_list.py'
with open(filepath, 'r') as f:
    code = f.read()

# We want to catch the error around evaluate_parameter_dict
new_code = code.replace("""
            params_set = evaluate_parameter_dict(
                context,
                params
            )""", """
            try:
                params_set = evaluate_parameter_dict(
                    context,
                    params
                )
            except TypeError as e:
                print(f"\n!!! CATASTROPHIC PARAMETER CRASH !!!")
                print(f"FAILED PARAMS DICT: {params}")
                raise e""")

with open(filepath, 'w') as f:
    f.write(new_code)
print('Patched to_parameters_list.py')
