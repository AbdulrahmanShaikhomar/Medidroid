#!/usr/bin/env python3
# IMU HEADING MEASUREMENT (motor-free). Hand-rotate the robot by KNOWN angles and
# compare. Tracks cumulative (unwrapped) EKF heading so a 90 deg turn reads ~90,
# a full 360 reads ~360 -- no wrap confusion. gyro_z sign = live rotation direction.
#   SIGN:  rotate LEFT/CCW  -> gyro_z POSITIVE, cumDyaw INCREASES (+).
#   SCALE: rotate exactly 90 deg -> cumDyaw ~ +/-90; full 360 -> ~ +/-360.
#   DRIFT: hold still -> cumDyaw should barely move.
import rclpy, math, time
from rclpy.node import Node
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry

def yaw_from_q(q):
    siny = 2.0 * (q.w * q.z + q.x * q.y)
    cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny, cosy)

class M(Node):
    def __init__(self):
        super().__init__('yaw_meas')
        self.gyro_z = 0.0; self.yaw = None; self.prev = None
        self.cum = 0.0; self.base = None; self.peak = 0.0
        self.create_subscription(Imu, '/imu/data_raw', self.imu, 30)
        self.create_subscription(Odometry, '/odometry/filtered', self.odo, 30)
        self.t0 = time.time()
        self.create_timer(0.2, self.tick)
    def imu(self, m): self.gyro_z = m.angular_velocity.z
    def odo(self, m):
        y = yaw_from_q(m.pose.pose.orientation)
        if self.prev is not None:
            d = y - self.prev
            if d > math.pi: d -= 2 * math.pi
            elif d < -math.pi: d += 2 * math.pi
            self.cum += d
        self.prev = y; self.yaw = y
        if self.base is None and (time.time() - self.t0) > 1.5:
            self.base = self.cum
    def tick(self):
        if self.yaw is None:
            print("waiting for /odometry/filtered ...", flush=True); return
        t = time.time() - self.t0
        base = self.base if self.base is not None else 0.0
        delta = math.degrees(self.cum - base)
        if abs(delta) > abs(self.peak): self.peak = delta
        flag = "   <== ROTATING" if abs(self.gyro_z) > 0.15 else ""
        print("t=%5.1f  gyro_z=%+6.3f rad/s  cumDyaw=%+8.1f deg   (peak %+8.1f)%s"
              % (t, self.gyro_z, delta, self.peak, flag), flush=True)

def main():
    rclpy.init(); n = M()
    try:
        rclpy.spin(n)
    except Exception:
        pass

if __name__ == '__main__':
    main()
