
import yaml

path = '/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml'
with open(path, 'r') as f:
    data = yaml.safe_load(f)

# Fix MPPI Controller Transform Tolerance
if 'controller_server' in data and 'ros__parameters' in data['controller_server']:
    params = data['controller_server']['ros__parameters']
    if 'FollowPath' in params:
        params['FollowPath']['transform_tolerance'] = 1.0

# Fix Collision Monitor Transform Tolerance
if 'collision_monitor' in data and 'ros__parameters' in data['collision_monitor']:
    data['collision_monitor']['ros__parameters']['transform_tolerance'] = 1.0

# Fix Inflation Radius (make it smaller so robot can pass through doors)
# global_costmap
if 'global_costmap' in data and 'global_costmap' in data['global_costmap']:
    g_params = data['global_costmap']['global_costmap']['ros__parameters']
    if 'inflation_layer' in g_params:
        g_params['inflation_layer']['inflation_radius'] = 0.25 # Reduced from 0.55
        g_params['inflation_layer']['cost_scaling_factor'] = 5.0 # Sharper dropoff

# local_costmap
if 'local_costmap' in data and 'local_costmap' in data['local_costmap']:
    l_params = data['local_costmap']['local_costmap']['ros__parameters']
    if 'inflation_layer' in l_params:
        l_params['inflation_layer']['inflation_radius'] = 0.25
        l_params['inflation_layer']['cost_scaling_factor'] = 5.0

with open(path, 'w') as f:
    yaml.dump(data, f, default_flow_style=False)
