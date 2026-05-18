import os
from launch import LaunchDescription
from launch.actions import TimerAction
from launch_ros.actions import Node, LifecycleNode
from launch_ros.actions import LifecycleNode

def generate_launch_description():
    return LaunchDescription([
        # --- 1. THE BODY (Connect Parts) ---
        # [DELETED] Static odom->base_link (This was the bug! We need real odom from motors)
        
        # Connect Body (base_link) -> Eyes (laser)
        # Keep this! It tells ROS where the laser is mounted.
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments = ['0.1', '0', '0.2', '0', '0', '0', 'base_link', 'laser']
        ),

        # --- 2. THE EYES (Lidar Driver) ---
        Node(
            package='sllidar_ros2',
            executable='sllidar_node',
            name='sllidar_node',
            output='screen',
            parameters=[{
                'channel_type': 'serial',
                'serial_port': '/dev/ttyUSB0',
                'serial_baudrate': 460800, # Verified from your file
                'frame_id': 'laser',
                'inverted': False,
                'angle_compensate': True
            }]
        ),

       # --- 3. THE LEGS (Motor Driver - REQUIRED) ---
       # You MUST run your motor driver here. 
       # If you use Micro-ROS (Arduino/ESP32), uncomment this:
       # Node(
       #     package='micro_ros_agent',
       #     executable='micro_ros_agent',
       #     name='micro_ros_agent',
       #     arguments=['serial', '--dev', '/dev/ttyACM0'],
       #     output='screen'
       # ),

       # --- 4. THE BRAIN (SLAM Toolbox) ---
        LifecycleNode(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            namespace='',
            parameters=[{
                'use_sim_time': False,
                'odom_frame': 'odom',
                'base_frame': 'base_link',
                'map_frame': 'map',
                'scan_topic': '/scan',
                'mode': 'mapping', 
                'transform_timeout': 1.0,
                'tf_buffer_duration': 2.0,
                'map_update_interval': 1.0 
            }]
        ),

        # --- 5. THE ALARM CLOCK (Wake Up Manager) ---
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
        )
    ])

