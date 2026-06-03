
import os

path = '/home/medidroid/ros2_ws/src/medidroid_base/medidroid_base/safety_gate.py'
with open(path, 'r') as f:
    content = f.read()

# Remove the faulty clamping logic that ruins turning in place
old_logic = '''            if v >= 0:
                pwm_l = max(pwm_l, 0)
                pwm_r = max(pwm_r, 0)
            else:
                pwm_l = min(pwm_l, 0)
                pwm_r = min(pwm_r, 0)
                '''

new_logic = ""

content = content.replace(old_logic, new_logic)

with open(path, 'w') as f:
    f.write(content)
