
import os
filepath = '/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/evaluate_parameters.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

out_lines = []
for line in lines:
    if line.startswith("        else:"):
        out_lines.append(line)
        out_lines.append("            # Value is a singular type, so nothing to evaluate\n")
        out_lines.append("            ensure_argument_type(value, (float, int, str, bool, bytes), 'value')\n")
        out_lines.append("            evaluated_value = cast(Union[float, int, str, bool, bytes], value)\n")
        out_lines.append("        if evaluated_value is None:\n")
        out_lines.append("            raise TypeError('given unnormalized parameters %r, %r' % (name, value))\n")
        out_lines.append("        output_dict[evaluated_name] = evaluated_value\n")
        out_lines.append("    return output_dict\n")
        break
    else:
        out_lines.append(line)

code = ''.join(out_lines)

# Re-apply our stderr patch cleanly!
target = """        else:
            # Value is a singular type, so nothing to evaluate
            ensure_argument_type(value, (float, int, str, bool, bytes), 'value')"""

replacement = """        else:
            # Value is a singular type, so nothing to evaluate
            try:
                ensure_argument_type(value, (float, int, str, bool, bytes), 'value')
            except TypeError as e:
                import sys
                print(f"PARAM CRASH: name={name} value={value} type={type(value)}", file=sys.stderr)
                raise e"""

code = code.replace(target, replacement)

with open(filepath, 'w') as f:
    f.write(code)
print('Fixed evaluate_parameters.py successfully!')
