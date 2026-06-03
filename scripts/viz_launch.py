#!/usr/bin/env python3
"""
viz_launch -- the T4 terminal, replacing software-RViz on the Pi.

  * foxglove_bridge : WebSocket server on :8765, but with a TOPIC WHITELIST so it
    only serves light topics (map, scan, tf, plan, pose, goals). The costmaps
    (/global_costmap/*, /local_costmap/* and their high-rate _updates) are the
    heavy streams that saturated the Pi (load 11.5 on 4 cores) and starved the
    Nav2 controller -> stutter -> robot couldn't break static friction. They're
    excluded here. You don't need them to see the map and click goals.
  * goal_relay      : /goal_pose + /move_base_simple/goal -> navigate_to_pose.

Run as:  ros2 launch /home/medidroid/viz_launch.py
"""
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node

WHITELIST = [
    "/map", "/scan", "/tf", "/tf_static",
    "/goal_pose", "/move_base_simple/goal", "/initialpose", "/clicked_point",
    "/plan", "/amcl_pose", "/odometry/filtered", "/robot_description", "/rosout",
]


def generate_launch_description():
    bridge = Node(
        package="foxglove_bridge",
        executable="foxglove_bridge",
        name="foxglove_bridge",
        output="screen",
        parameters=[{
            "port": 8765,
            "address": "0.0.0.0",
            "topic_whitelist": WHITELIST,
            "send_buffer_limit": 10000000,
            "use_compression": False,   # CPU is the bottleneck, not bandwidth
            "max_qos_depth": 5,
        }],
    )
    relay = ExecuteProcess(
        cmd=["python3", "-u", "/home/medidroid/goal_relay.py"],
        output="screen")
    return LaunchDescription([bridge, relay])
