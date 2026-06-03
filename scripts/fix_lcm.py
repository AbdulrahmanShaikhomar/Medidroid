
import yaml

user_path = '/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml'

with open(user_path, 'r') as f:
    user_data = yaml.safe_load(f)

# Add lifecycle_manager_localization section with longer timeouts
user_data['lifecycle_manager_localization'] = {
    'ros__parameters': {
        'autostart': True,
        'bond_timeout': 40.0,
        'attempt_respawn_reconnection': True,
        'bond_respawn_max_duration': 10.0,
        'node_names': ['map_server', 'amcl'],
    }
}

# Add lifecycle_manager_navigation section with longer timeouts
user_data['lifecycle_manager_navigation'] = {
    'ros__parameters': {
        'autostart': True,
        'bond_timeout': 40.0,
        'attempt_respawn_reconnection': True,
        'bond_respawn_max_duration': 10.0,
        'node_names': [
            'controller_server',
            'smoother_server',
            'planner_server',
            'route_server',
            'behavior_server',
            'velocity_smoother',
            'collision_monitor',
            'bt_navigator',
            'waypoint_follower',
            'docking_server',
        ],
    }
}

with open(user_path, 'w') as f:
    yaml.dump(user_data, f)

print("Done patching lifecycle manager timeouts")
