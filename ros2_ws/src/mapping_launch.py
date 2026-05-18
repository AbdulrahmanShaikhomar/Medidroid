from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 1. Start the Lidar Driver (C1 Mode)
        Node(
            package='sllidar_ros2',
            executable='sllidar_node',
            name='sllidar_node',
            parameters=[{'channel_type': 'serial',
                         'serial_port': '/dev/ttyUSB0',
                         'serial_baudrate': 460800,
                         'frame_id': 'laser',
                         'inverted': False,
                         'angle_compensate': True}],
            output='screen'
        ),

        # 2. Static TF: Connect Fake Wheels (odom) -> Body (base_link)
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments = ['0', '0', '0', '0', '0', '0', 'odom', 'base_link']
        ),

        # 3. Static TF: Connect Body (base_link) -> Lidar (laser)
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            arguments = ['0.1', '0', '0.2', '0', '0', '0', 'base_link', 'laser']
        ),

        # 4. Start SLAM Toolbox
        Node(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            parameters=[
               {'use_sim_time': False},
               {'odom_frame': 'odom'},
               {'base_frame': 'base_link'},
               {'map_frame': 'map'},
               {'scan_topic': '/scan'}
            ]
        )
    ])
