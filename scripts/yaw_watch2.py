#!/usr/bin/env python3
# Live yaw-loop watcher. Prints every 0.2s:
#   cmd_w  = /cmd_vel angular.z   (direction the controller WANTS to turn)
#   gyro_z = /imu/data_raw .z     (RAW gyro: robot's REAL rotation rate)
#   ekf_wz = /odometry/filtered twist.z (yaw-rate the controller READS BACK)
#   ekf_yaw= integrated EKF heading (deg)
# Inversion test: when the robot physically turns LEFT/CCW, gyro_z and ekf_wz must
# be POSITIVE and ekf_yaw must INCREASE. If they go negative while it turns left,
# the IMU yaw sign is flipped -> the controller chases its tail -> endless spin.
import rclpy, math, time
from rclpy.node import Node
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist

def yaw_from_q(q):
    siny = 2.0 * (q.w * q.z + q.x * q.y)
    cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny, cosy)

class W(Node):
    def __init__(self):
        super().__init__('yaw_watch2')
        self.cmd_w = 0.0; self.gyro_z = 0.0; self.ekf_yaw = 0.0; self.ekf_wz = 0.0
        self.cmd_age = 99.0; self.last_cmd = time.time()
        self.create_subscription(Imu, '/imu/data_raw', self.imu, 20)
        self.create_subscription(Odometry, '/odometry/filtered', self.odo, 20)
        self.create_subscription(Twist, '/cmd_vel', self.cmd, 20)
        self.t0 = time.time()
        self.create_timer(0.2, self.tick)
    def imu(self, m): self.gyro_z = m.angular_velocity.z
    def odo(self, m):
        self.ekf_yaw = math.degrees(yaw_from_q(m.pose.pose.orientation))
        self.ekf_wz = m.twist.twist.angular.z
    def cmd(self, m): self.cmd_w = m.angular.z; self.last_cmd = time.time()
    def tick(self):
        t = time.time() - self.t0
        age = time.time() - self.last_cmd
        cw = self.cmd_w if age < 0.6 else 0.0   # show 0 if no fresh cmd (watchdog stop)
        print("t=%5.1f  cmd_w=%+6.3f  gyro_z=%+6.3f  ekf_wz=%+6.3f  ekf_yaw=%+7.1f"
              % (t, cw, self.gyro_z, self.ekf_wz, self.ekf_yaw), flush=True)

def main():
    rclpy.init(); n = W()
    try:
        rclpy.spin(n)
    except Exception:
        pass

if __name__ == '__main__':
    main()
