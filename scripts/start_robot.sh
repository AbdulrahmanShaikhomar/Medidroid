#!/bin/bash

echo "--- KILLING OLD PROCESSES ---"
pkill -f ros2
pkill -f sllidar
pkill -f slam_toolbox
sleep 2

echo "--- 1. STARTING LIDAR (C1) ---"
# Launches the official C1 driver in the background
ros2 launch sllidar_ros2 sllidar_c1_launch.py serial_port:=/dev/ttyUSB1 &
PID_LIDAR=$!
sleep 5  # Give it 5 seconds to spin up

echo "--- 2. STARTING TRANSFORMS ---"
# Connects Fake Wheels (odom) -> Body (base_link)
ros2 run tf2_ros static_transform_publisher --frame-id odom --child-frame-id base_link --x 0 --y 0 --z 0 --yaw 0 --pitch 0 --roll 0 &

# Connects Body (base_link) -> Eyes (laser)
ros2 run tf2_ros static_transform_publisher --frame-id base_link --child-frame-id laser --x 0.1 --y 0 --z 0.2 --yaw 0 --pitch 0 --roll 0 &
sleep 2

echo "--- 3. STARTING SLAM ---"
# Starts the mapping brain
ros2 launch slam_toolbox online_async_launch.py
