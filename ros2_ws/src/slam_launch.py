import os
from launch import LaunchDescription
from launch_ros.actions import LifecycleNode, Node

def generate_launch_description():

    params_file = '/home/medidroid/ros2_ws/src/slam_params.yaml'

    return LaunchDescription([

        # SLAM Toolbox — builds the map using /scan + /odom
        # NOTE: LiDAR and TF are provided by nav_hardware_launch.py
        LifecycleNode(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            namespace='',
            parameters=[params_file]
        ),

        # Lifecycle manager — auto-starts slam_toolbox
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_slam',
            output='screen',
            parameters=[{
                'use_sim_time': False,
                'autostart': True,
                'node_names': ['slam_toolbox'],
                'bond_timeout': 20.0
            }]
        ),
    ])
