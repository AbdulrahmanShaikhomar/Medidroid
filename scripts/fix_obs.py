
import yaml

user_path = '/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml'

with open(user_path, 'r') as f:
    user_data = yaml.safe_load(f)

# Fix local_costmap
if 'local_costmap' in user_data and 'local_costmap' in user_data['local_costmap']:
    voxel_layer = user_data['local_costmap']['local_costmap']['ros__parameters']['voxel_layer']
    if 'observation_sources' in voxel_layer and isinstance(voxel_layer['observation_sources'], list):
        voxel_layer['observation_sources'] = "scan"

# Fix global_costmap
if 'global_costmap' in user_data and 'global_costmap' in user_data['global_costmap']:
    obstacle_layer = user_data['global_costmap']['global_costmap']['ros__parameters']['obstacle_layer']
    if 'observation_sources' in obstacle_layer and isinstance(obstacle_layer['observation_sources'], list):
        obstacle_layer['observation_sources'] = "scan"

# Ensure collision_monitor is a list (this one actually is a list in C++)
if 'collision_monitor' in user_data:
    cm_params = user_data['collision_monitor']['ros__parameters']
    if 'observation_sources' in cm_params and isinstance(cm_params['observation_sources'], str):
        cm_params['observation_sources'] = ["scan"]

with open(user_path, 'w') as f:
    yaml.dump(user_data, f)
