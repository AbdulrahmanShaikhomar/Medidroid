
import yaml

with open('/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml', 'r') as f:
    data = yaml.safe_load(f)

def find_obs(d, path):
    if isinstance(d, dict):
        for k, v in d.items():
            find_obs(v, path + [str(k)])
    elif isinstance(d, list):
        for i, v in enumerate(d):
            find_obs(v, path + [str(i)])
    else:
        if path and path[-1] == 'observation_sources':
            print(f"Path: {'.'.join(path)} = {repr(d)}")

find_obs(data, [])
