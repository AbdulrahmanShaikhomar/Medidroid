from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import os


def generate_launch_description():
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    medidroid_base_dir = get_package_share_directory('medidroid_base')

    params_file = os.path.join(medidroid_base_dir, 'config', 'nav2_params.yaml')
    map_yaml_file = LaunchConfiguration('map')

    # Nav2 full bringup (map_server + amcl + all nav nodes)
    bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')
        ),
        launch_arguments=[
            ('use_sim_time', 'false'),
            ('params_file', params_file),
            ('map', map_yaml_file),
        ]
    )

    # Pose manager (saves/restores robot pose across restarts)
    pose_manager = Node(
        package='medidroid_base',
        executable='pose_manager',
        name='pose_manager',
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'map',
            default_value='/home/medidroid/my_home_map.yaml',
            description='Full path to map yaml file'),
        bringup_launch,
        pose_manager,
    ])
