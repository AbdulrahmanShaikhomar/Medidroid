
import yaml

orig_path = '/opt/ros/jazzy/share/nav2_bringup/params/nav2_params.yaml'
user_path = '/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml'

with open(orig_path, 'r') as f:
    orig_data = yaml.safe_load(f)

with open(user_path, 'r') as f:
    user_data = yaml.safe_load(f)

# The controller_server seems to be missing vital parameters like controller_plugins.
# Let's completely restore it from the original.
user_data['controller_server'] = orig_data['controller_server']

with open(user_path, 'w') as f:
    yaml.dump(user_data, f)
