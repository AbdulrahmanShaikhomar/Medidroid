
import yaml

# Load original nav2_params.yaml
with open('/opt/ros/jazzy/share/nav2_bringup/params/nav2_params.yaml', 'r') as f:
    orig_data = yaml.safe_load(f)

# Load our nav2_params.yaml
user_path = '/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml'
with open(user_path, 'r') as f:
    user_data = yaml.safe_load(f)

# Copy collision monitor
user_data['collision_monitor'] = orig_data['collision_monitor']

# We just need to make sure collision_monitor uses cmd_vel_smoothed -> cmd_vel
# Wait, original uses cmd_vel_in_topic: "cmd_vel_smoothed", cmd_vel_out_topic: "cmd_vel"
user_data['collision_monitor']['ros__parameters']['cmd_vel_in_topic'] = "cmd_vel_smoothed"
user_data['collision_monitor']['ros__parameters']['cmd_vel_out_topic'] = "cmd_vel"
user_data['collision_monitor']['ros__parameters']['base_frame_id'] = "base_link"
user_data['collision_monitor']['ros__parameters']['odom_frame_id'] = "odom"

# Write back
with open(user_path, 'w') as f:
    yaml.dump(user_data, f)
