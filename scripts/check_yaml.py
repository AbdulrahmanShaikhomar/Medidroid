
import yaml

def check_dict(d, path=''):
    for k, v in d.items():
        curr_path = f"{path}.{k}" if path else k
        if isinstance(v, dict):
            check_dict(v, curr_path)
        elif isinstance(v, list):
            if len(v) == 0:
                print(f"EMPTY LIST AT: {curr_path}")
        elif isinstance(v, tuple):
            print(f"TUPLE AT: {curr_path}")

with open('/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml', 'r') as f:
    data = yaml.safe_load(f)

check_dict(data)
