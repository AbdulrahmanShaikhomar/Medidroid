
import os

path = '/home/medidroid/ros2_ws/src/medidroid_base/medidroid_base/safety_gate.py'
with open(path, 'r') as f:
    content = f.read()

old_logic = '''            base_pwm = v * LINEAR_SCALE
            turn_diff = w * ANGULAR_SCALE
            pwm_l = base_pwm - turn_diff
            pwm_r = base_pwm + turn_diff'''

new_logic = '''            # User requested full speed for turning
            if abs(v) < 0.05 and abs(w) > 0.05:
                # Pure rotation (turn left/right) -> Full Speed 255
                pwm_l = -255 if w > 0 else 255
                pwm_r = 255 if w > 0 else -255
            else:
                # Normal proportional movement for forward/backward
                base_pwm = v * LINEAR_SCALE
                turn_diff = w * ANGULAR_SCALE
                pwm_l = base_pwm - turn_diff
                pwm_r = base_pwm + turn_diff'''

if old_logic in content:
    content = content.replace(old_logic, new_logic)
    with open(path, 'w') as f:
        f.write(content)
    print("Patched turning logic in safety_gate.py")
else:
    print("Could not find old_logic block")
