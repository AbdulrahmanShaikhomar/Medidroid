#!/usr/bin/env python3
"""
Saves the robot's last known AMCL pose to disk and restores it on the next
startup — so the robot never needs a manual "2D Pose Estimate" in RViz again.

Pose file: ~/.ros/medidroid_last_pose.yaml
"""
import math
import os
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
import yaml

POSE_FILE = os.path.expanduser('~/.ros/medidroid_last_pose.yaml')


class PoseManager(Node):
    def __init__(self):
        super().__init__('pose_manager')

        self._pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)

        # Save pose every time AMCL updates its estimate
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self._on_amcl_pose, 10)

        # Publish saved pose once, 4 seconds after startup (gives Nav2 time to start)
        self._restore_timer = self.create_timer(4.0, self._restore_pose)
        self._restored = False

    # ── Save ──────────────────────────────────────────────────────────────────

    def _on_amcl_pose(self, msg: PoseWithCovarianceStamped):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        oz = msg.pose.pose.orientation.z
        ow = msg.pose.pose.orientation.w
        yaw = 2.0 * math.atan2(oz, ow)
        os.makedirs(os.path.dirname(POSE_FILE), exist_ok=True)
        with open(POSE_FILE, 'w') as f:
            yaml.dump({'x': float(x), 'y': float(y), 'yaw': float(yaw)}, f)

    # ── Restore ───────────────────────────────────────────────────────────────

    def _restore_pose(self):
        self._restore_timer.cancel()
        if self._restored:
            return
        self._restored = True

        if not os.path.exists(POSE_FILE):
            self.get_logger().warn(
                'No saved pose found — set your starting position once in RViz '
                '(2D Pose Estimate). It will be remembered from then on.')
            return

        with open(POSE_FILE) as f:
            data = yaml.safe_load(f)

        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = data['x']
        msg.pose.pose.position.y = data['y']
        yaw = data['yaw']
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        # Slightly generous covariance so AMCL can still correct if the robot
        # was moved while powered off
        msg.pose.covariance[0]  = 0.25   # x
        msg.pose.covariance[7]  = 0.25   # y
        msg.pose.covariance[35] = 0.10   # yaw

        self._pub.publish(msg)
        self.get_logger().info(
            f'Restored pose: x={data["x"]:.2f} y={data["y"]:.2f} '
            f'yaw={math.degrees(data["yaw"]):.1f}°')


def main(args=None):
    rclpy.init(args=args)
    node = PoseManager()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
