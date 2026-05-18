import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 1. LiDAR Node
        Node(
            package='sllidar_ros2',
            executable='sllidar_node',
            name='sllidar_node',
            parameters=[{
                'channel_type': 'serial',
                'serial_port': '/dev/ttyLIDAR',
                'serial_baudrate': 460800,
                'frame_id': 'laser',
                'inverted': False,
                'angle_compensate': True
            }],
            arguments=['--ros-args', '-p', 'qos_profile.reliability:=reliable'],
            output='screen'
        ),
        
        # 2. Static Transform (Base -> Laser)
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='static_transform_publisher',
            arguments=['0.1', '0', '0.2', '3.14159', '0', '0', 'base_link', 'laser'],
            output='screen'
        ),

        # 3. LiDAR-based Odometry
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
                'freq': 10.0,
            }],
        ),
    ])
