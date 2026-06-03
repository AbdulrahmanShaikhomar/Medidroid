
import yaml

# Load default SLAM toolbox params
default_params = '/opt/ros/jazzy/share/slam_toolbox/config/mapper_params_online_async.yaml'
with open(default_params, 'r') as f:
    data = yaml.safe_load(f)

# Modify for Raspberry Pi (relax timeouts)
if 'slam_toolbox' in data and 'ros__parameters' in data['slam_toolbox']:
    params = data['slam_toolbox']['ros__parameters']
    params['transform_timeout'] = 1.0  # Increased from 0.2
    params['tf_buffer_duration'] = 5.0 # Increased buffer
    params['max_laser_range'] = 8.0    # Optimize processing
    
# Save to custom file
custom_params = '/home/medidroid/my_slam_params.yaml'
with open(custom_params, 'w') as f:
    yaml.dump(data, f, default_flow_style=False)
