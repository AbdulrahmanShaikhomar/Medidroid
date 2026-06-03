
import yaml
from launch import LaunchContext
from launch_ros.utilities.evaluate_parameters import evaluate_parameter_dict

with open('/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml', 'r') as f:
    data = yaml.safe_load(f)

context = LaunchContext()
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
        evaluate_parameter_dict(context, params)
    except Exception as e:
        print(f"CRASH in node {node_name}!")
        import traceback
        traceback.print_exc()
