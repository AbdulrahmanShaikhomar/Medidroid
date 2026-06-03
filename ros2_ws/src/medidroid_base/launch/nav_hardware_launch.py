"""
MediDroid CANONICAL hardware bringup  (LiDAR + IMU-fused odometry, NO Nav2, NO wheel motion).

This is the ONE hardware launch. All three names point at identical content
(nav_hardware_launch.py at the src root, the package copy, and imu_hardware_launch.py)
so whichever command muscle-memory reaches for, you get the SAME correct stack with
exactly ONE publisher of odom->base_link (the EKF). Running the old rotation-blind
rf2o-publish_tf version alongside the EKF would create two fighting TF publishers —
that footgun is now removed.

  Terminal 1:  ros2 launch /home/medidroid/ros2_ws/src/nav_hardware_launch.py
  Terminal 2:  ros2 run medidroid_base safety_gate
  Terminal 3:  ros2 launch medidroid_base nav_launch.py map:=/home/medidroid/mapp.yaml
  Terminal 4:  export LIBGL_ALWAYS_SOFTWARE=1 && rviz2

Sensor design (why this layout):
  * Heading/yaw  -> MPU9255 gyro (IMU). rf2o laser-odometry is BLIND to in-place
    rotation; the gyro is not. This is the fix for "turns forever / pose rotates
    while still". The IMU is the authority on rotation.
  * Translation X/Y -> rf2o laser odometry. An IMU CANNOT measure position
    (accelerometer double-integration drifts in seconds), so the LiDAR supplies
    translation. The LiDAR therefore does triple duty: rf2o translation, AMCL
    localization, and costmap obstacle avoidance.
  * The EKF (robot_localization) fuses gyro-yaw + rf2o-XY into odom->base_link.
  * Nav2 AMCL adds map->odom by matching /scan to the static map.
"""
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    ekf_yaml = '/home/medidroid/ekf.yaml'
    return LaunchDescription([
        # 1. LiDAR (RPLIDAR C1) -> /scan
        Node(
            package='sllidar_ros2', executable='sllidar_node', name='sllidar_node',
            parameters=[{
                'channel_type': 'serial',
                'serial_port': '/dev/ttyLIDAR',
                'serial_baudrate': 460800,
                'frame_id': 'laser',
                'inverted': False,
                'angle_compensate': True,
            }],
            arguments=['--ros-args', '-p', 'qos_profile.reliability:=reliable'],
            output='screen',
        ),

        # 2. base_link -> laser  (yaw=pi: LiDAR mounted BACKWARD; matches the map the
        #    robot was built against. DO NOT change this yaw or AMCL can never localize.)
        Node(
            package='tf2_ros', executable='static_transform_publisher', name='tf_base_laser',
            arguments=['0.1', '0', '0.2', '3.14159', '0', '0', 'base_link', 'laser'],
            output='screen',
        ),

        # 3. base_link -> imu_link  (IMU is X-fwd, Y-left, Z-up => identity rotation)
        Node(
            package='tf2_ros', executable='static_transform_publisher', name='tf_base_imu',
            arguments=['0', '0', '0.1', '0', '0', '0', 'base_link', 'imu_link'],
            output='screen',
        ),

        # 4. rf2o laser odometry: publishes /odom (X/Y) ONLY, NO TF.
        #    publish_tf=False is critical — the EKF owns odom->base_link. If rf2o also
        #    published it, two nodes would fight over the same transform.
        Node(
            package='rf2o_laser_odometry', executable='rf2o_laser_odometry_node',
            name='rf2o_laser_odometry', output='screen',
            parameters=[{
                'laser_scan_topic': '/scan',
                'odom_topic': '/odom',
                'publish_tf': False,
                'base_frame_id': 'base_link',
                'odom_frame_id': 'odom',
                'init_pose_from_topic': '',
                'freq': 10.0,
            }],
        ),

        # 5. MPU9255 IMU node -> /imu/data_raw @100Hz (stdlib I2C, no pip deps).
        #    Calibrates gyro bias ONCE at startup — the robot MUST be still for ~1.5s
        #    when this launches. -u = unbuffered so its log lines flush immediately.
        ExecuteProcess(
            cmd=['python3', '-u', '/home/medidroid/imu_mpu9255_node.py'],
            output='screen',
        ),

        # 6. robot_localization EKF: fuse rf2o(X,Y) + IMU(yaw-rate) -> odom->base_link
        #    + /odometry/filtered. This is the single source of odom->base_link.
        Node(
            package='robot_localization', executable='ekf_node', name='ekf_filter_node',
            output='screen', parameters=[ekf_yaml],
        ),
    ])
