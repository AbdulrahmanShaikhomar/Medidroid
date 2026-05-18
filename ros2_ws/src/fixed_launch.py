import os
from launch import LaunchDescription
from launch_ros.actions import Node, LifecycleNode
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    
    # Hardcoded path ensures it works no matter where the launch command is executed from
    params_file = '/home/medidroid/ros2_ws/src/slam_params.yaml'


    return LaunchDescription([
        # --- 1. THE BODY ---
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments = ['0.1', '0', '0.2', '0', '0', '0', 'base_link', 'laser']
        ),

        # --- 2. THE EYES ---
        Node(
            package='sllidar_ros2',
            executable='sllidar_node',
            name='sllidar_node',
            output='screen',
            parameters=[{
                'channel_type': 'serial',
                'serial_port': '/dev/ttyLIDAR',
                'serial_baudrate': 460800,
                'frame_id': 'laser',
                'inverted': False,
                'angle_compensate': True
            }],
            arguments=['--ros-args', '-p', 'qos_profile.reliability:=reliable'] 
        ),

       # --- 3. THE INNER EAR (RF2O) ---
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

       # --- 4. THE BRAIN (SLAM Toolbox - TUNED) ---
        LifecycleNode(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            namespace='',
            # UPDATED: Load parameters from the external YAML file
            parameters=[params_file] 
        ),

        # --- 5. THE ALARM CLOCK ---
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
