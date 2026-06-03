
import os

# 1. Revert nav_launch.py
nav_launch_path = '/home/medidroid/ros2_ws/src/medidroid_base/launch/nav_launch.py'
with open(nav_launch_path, 'r') as f:
    nav_code = f.read()

nav_code = nav_code.replace('from launch_ros.actions import Node, SetRemap', 'from launch_ros.actions import Node')
nav_code = nav_code.replace("    remap_cmd_vel = SetRemap(src='cmd_vel_smoothed', dst='cmd_vel')\n", "")
nav_code = nav_code.replace("        remap_cmd_vel,\n", "")

with open(nav_launch_path, 'w') as f:
    f.write(nav_code)

# 2. Add collision_monitor to nav2_params.yaml
params_path = '/home/medidroid/ros2_ws/src/medidroid_base/config/nav2_params.yaml'
with open(params_path, 'r') as f:
    params_code = f.read()

if "collision_monitor:" not in params_code:
    collision_block = """
collision_monitor:
  ros__parameters:
    base_frame_id: "base_link"
    odom_frame_id: "odom"
    cmd_vel_in_topic: "cmd_vel_smoothed"
    cmd_vel_out_topic: "cmd_vel"
    state_topic: "velocity_smoother/transition_event"
    transform_tolerance: 0.2
    source_timeout: 1.0
    base_shift_correction: True
    stop_pub_timeout: 2.0
    polygons: ["PolygonStop"]
    PolygonStop:
      type: "polygon"
      points: [[0.3, 0.3], [0.3, -0.3], [-0.3, -0.3], [-0.3, 0.3]]
      action_type: "stop"
      max_points: 3
      visualize: False
      enabled: True
    observation_sources: ["scan"]
    scan:
      type: "scan"
      topic: "/scan"
      min_height: 0.15
      max_height: 2.0
"""
    with open(params_path, 'a') as f:
        f.write(collision_block)
