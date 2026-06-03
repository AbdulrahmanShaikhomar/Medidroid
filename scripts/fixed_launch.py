import os
from launch import LaunchDescription
from launch_ros.actions import Node, LifecycleNode

def generate_launch_description():
    return LaunchDescription([
        # --- 1. THE BODY (Connect Parts) ---
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments = ['0.1', '0', '0.2', '0', '0', '0', 'base_link', 'laser']
        ),

        # --- 2. THE EYES (Lidar Driver) ---
        # UPDATED: Added QoS settings to ensure it talks to RF2O
        Node(
            package='sllidar_ros2',
            executable='sllidar_node',
            name='sllidar_node',
            output='screen',
            parameters=[{
                'channel_type': 'serial',
                'serial_port': '/dev/ttyUSB1',
                'serial_baudrate': 460800,
                'frame_id': 'laser',
                'inverted': False,
                'angle_compensate': True
            }],
            # Force "Reliable" communication so RF2O can hear it
            arguments=['--ros-args', '-p', 'qos_profile.reliability:=reliable'] 
        ),

       # --- 3. THE INNER EAR (Laser Odometry - RF2O) ---
       Node(
            package='rf2o_laser_odometry',
            executable='rf2o_laser_odometry_node',
            name='rf2o_laser_odometry',
            output='screen',
            parameters=[{
                'laser_scan_topic': '/scan',
                'odom_topic': '/odom',
                'publish_tf': True, 
                'base_frame_id': 'base_link',
                'odom_frame_id': 'odom',
                'init_pose_from_topic': '',
                'freq': 40.0
            }]
       ),

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
                'transform_timeout': 0.1,
                'tf_buffer_duration': 5.0,
                'map_update_interval': 0.1,
                'resolution': 0.05,
                'max_laser_range': 20.0, 
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
