
import yaml
from launch_ros.utilities.normalize_parameters import normalize_parameter_dict

with open('/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml', 'r') as f:
    data = yaml.safe_load(f)

for node_name, node_data in data.items():
    if not node_data: continue
    if 'ros__parameters' in node_data:
        params = node_data['ros__parameters']
    elif node_name in node_data and 'ros__parameters' in node_data[node_name]:
        params = node_data[node_name]['ros__parameters']
    else: continue

    try:
        normalized = normalize_parameter_dict(params)
        for k, v in normalized.items():
            k_str = k[-1].text if k else str(k)
            if k_str == 'observation_sources':
                print(f"Node: {node_name}, observation_sources = {v}")
    except Exception as e:
        pass
