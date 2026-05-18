#!/bin/bash
# MediDroid Clean Launch Helper
# Run this before launching nav_launch.py to guarantee a clean slate

echo "[medidroid] Cleaning up stale ROS processes..."

pkill -9 component_container_isolated 2>/dev/null
pkill -9 component_container 2>/dev/null
pkill -9 sllidar_node 2>/dev/null
pkill -9 rf2o_laser_odometry_node 2>/dev/null
pkill -9 controller_server 2>/dev/null
pkill -9 pose_manager 2>/dev/null
pkill -9 static_transform_publisher 2>/dev/null
pkill -9 -f "nav_launch.py" 2>/dev/null
pkill -9 -f "ros2 topic hz" 2>/dev/null
pkill -9 -f "ros2 lifecycle" 2>/dev/null

sleep 2

# Clear stale FastRTPS shared memory
rm -f /dev/shm/sem.fastrtps_* 2>/dev/null

echo "[medidroid] Done. Starting navigation..."
sleep 1

source /opt/ros/jazzy/setup.bash
source /home/medidroid/ros2_ws/install/setup.bash
ros2 launch medidroid_base nav_launch.py "$@"
