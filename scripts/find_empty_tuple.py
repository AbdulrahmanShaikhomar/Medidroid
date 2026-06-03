
import yaml
from launch import LaunchContext
from launch_ros.utilities.normalize_parameters import normalize_parameter_dict

with open('/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml', 'r') as f:
    data = yaml.safe_load(f)

for node_name, node_data in data.items():
    if not node_data:
        continue
    if 'ros__parameters' in node_data:
        params = node_data['ros__parameters']
    elif node_name in node_data and 'ros__parameters' in node_data[node_name]:
        params = node_data[node_name]['ros__parameters']
    else:
        continue
    
    try:
        normalized = normalize_parameter_dict(params)
        for k, v in normalized.items():
            if isinstance(v, tuple) and len(v) == 0:
                print(f"!!! FOUND EMPTY TUPLE in node {node_name}: key={k}")
    except Exception as e:
        print(f"Error normalizing {node_name}: {e}")
