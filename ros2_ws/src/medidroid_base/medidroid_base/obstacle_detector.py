#!/usr/bin/env python3
"""
MediDroid - Simple Distance Warning
If ANYTHING is closer than 5cm, warn.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
import math

class ObstacleDetector(Node):
    def __init__(self):
        super().__init__('obstacle_detector')
        self.sub = self.create_subscription(LaserScan, '/scan', self.callback, 10)
        self.threshold = 0.05  # 5cm for testing
        self.get_logger().info(f'WARNING if anything < {self.threshold}m (5cm)')

    def callback(self, msg):
        for i, d in enumerate(msg.ranges):
            if math.isinf(d) or math.isnan(d):
                continue
            if d < self.threshold:
                angle = math.degrees(msg.angle_min + i * msg.angle_increment)
                self.get_logger().warn(f'OBJECT at {d:.3f}m  angle={angle:.0f}deg')
                return  # Only print once per scan

def main(args=None):
    rclpy.init(args=args)
    node = ObstacleDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
