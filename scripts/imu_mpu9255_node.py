#!/usr/bin/env python3
"""
MediDroid IMU node -- MPU9255 (MPU9250-register-compatible) on /dev/i2c-1 @ 0x68.
Publishes sensor_msgs/Imu (gyro + accel) on /imu/data_raw at ~100 Hz.

No external deps: talks I2C via fcntl ioctl (Python stdlib only), exactly like
imu_probe.py -- so nothing needs to be pip-installed on the Pi.

Orientation is NOT estimated here: orientation_covariance[0] = -1.0 (REP-145),
which tells imu_filter_madgwick / robot_localization "gyro+accel only". Downstream
can run a filter, or integrate angular_velocity.z for relative yaw.

Gyro bias is sampled at startup (robot MUST be still ~1.5 s) and then tracked
continuously: whenever the robot is not rotating, the bias estimate is nudged
toward the live reading so slow thermal drift can't accumulate. A small rate
deadband then snaps sub-threshold residual to exactly 0 so the EKF yaw never
creeps while the robot is at rest (kills the ~3 deg/min one-way pose rotation).
"""
import fcntl
import os
import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

# ---- I2C low-level ----
I2C_SLAVE = 0x0703
BUS_PATH = "/dev/i2c-1"
ADDR = 0x68

# ---- MPU9255 / MPU9250 registers ----
REG_SMPLRT_DIV = 0x19
REG_CONFIG = 0x1A
REG_GYRO_CONFIG = 0x1B
REG_ACCEL_CONFIG = 0x1C
REG_ACCEL_CONFIG2 = 0x1D
REG_ACCEL_XOUT_H = 0x3B
REG_PWR_MGMT_1 = 0x6B
REG_PWR_MGMT_2 = 0x6C
REG_WHO_AM_I = 0x75

GRAV = 9.80665  # m/s^2 per g

WHOAMI = {0x71: "MPU9250", 0x73: "MPU9255", 0x70: "MPU6500 (clone, no mag)",
          0x68: "MPU6050/6500-family"}


class MPU9255:
    """Minimal MPU9255 driver over the i2c-dev char device (stdlib only)."""

    def __init__(self, bus=BUS_PATH, addr=ADDR):
        self.fd = os.open(bus, os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, addr)
        self.addr = addr
        self.gyro_scale = 1.0 / 65.5      # dps per LSB (set in init)
        self.accel_scale = 1.0 / 16384.0  # g   per LSB (set in init)

    def _w(self, reg, val):
        os.write(self.fd, bytes([reg, val]))

    def _r(self, reg, n=1):
        os.write(self.fd, bytes([reg]))
        return os.read(self.fd, n)

    def whoami(self):
        return self._r(REG_WHO_AM_I, 1)[0]

    def init(self):
        self._w(REG_PWR_MGMT_1, 0x80)          # reset
        time.sleep(0.1)
        self._w(REG_PWR_MGMT_1, 0x01)          # wake, auto clock (gyro PLL)
        time.sleep(0.01)
        self._w(REG_PWR_MGMT_2, 0x00)          # all axes on
        time.sleep(0.01)
        self._w(REG_CONFIG, 0x03)              # gyro DLPF ~41 Hz
        self._w(REG_SMPLRT_DIV, 0x09)          # 1000/(1+9) = 100 Hz
        self._w(REG_GYRO_CONFIG, 0x08)         # +/-500 dps, DLPF enabled
        self._w(REG_ACCEL_CONFIG, 0x00)        # +/-2 g
        self._w(REG_ACCEL_CONFIG2, 0x03)       # accel DLPF ~41 Hz
        time.sleep(0.05)
        self.gyro_scale = 1.0 / 65.5           # +/-500 dps
        self.accel_scale = 1.0 / 16384.0       # +/-2 g

    @staticmethod
    def _s16(h, l):
        v = (h << 8) | l
        return v - 65536 if v >= 32768 else v

    def read(self):
        """Return (ax,ay,az [m/s^2], gx,gy,gz [deg/s]). One 14-byte burst."""
        d = self._r(REG_ACCEL_XOUT_H, 14)
        ax = self._s16(d[0], d[1]); ay = self._s16(d[2], d[3]); az = self._s16(d[4], d[5])
        # d[6],d[7] = temperature (ignored)
        gx = self._s16(d[8], d[9]); gy = self._s16(d[10], d[11]); gz = self._s16(d[12], d[13])
        a = self.accel_scale * GRAV
        return (ax * a, ay * a, az * a,
                gx * self.gyro_scale, gy * self.gyro_scale, gz * self.gyro_scale)

    def close(self):
        try:
            os.close(self.fd)
        except Exception:
            pass


def _clamp(v, lim):
    """Clamp v to [-lim, +lim] so a tracked bias can never run away."""
    if v > lim:
        return lim
    if v < -lim:
        return -lim
    return v


class ImuNode(Node):
    def __init__(self):
        super().__init__("imu_mpu9255")
        self.declare_parameter("frame_id", "imu_link")
        self.declare_parameter("topic", "/imu/data_raw")
        self.declare_parameter("rate_hz", 100.0)
        self.frame_id = self.get_parameter("frame_id").value
        topic = self.get_parameter("topic").value
        rate = float(self.get_parameter("rate_hz").value)

        self.dev = MPU9255()
        wai = self.dev.whoami()
        label = WHOAMI.get(wai, "unknown (0x%02x)" % wai)
        self.get_logger().info("WHO_AM_I=0x%02x -> %s" % (wai, label))
        if wai not in (0x71, 0x73):
            self.get_logger().warn("Unexpected WHO_AM_I -- continuing anyway (gyro/accel still work).")
        self.dev.init()

        # gyro bias: average N samples while stationary
        self.get_logger().info("Calibrating gyro bias -- keep the robot STILL (~1.5 s)...")
        self.bias = list(self._calibrate(300))
        self.get_logger().info("Gyro bias (deg/s): x=%.3f y=%.3f z=%.3f"
                               % (self.bias[0], self.bias[1], self.bias[2]))

        # ---- gyro rest-drift suppression (kills the ~3 deg/min EKF yaw creep) ----
        # Root cause: the one-shot startup cal leaves a residual DC offset, and the
        # MEMS bias itself drifts as the chip warms. A constant ~0.05 deg/s offset
        # integrates to ~3 deg/min, always one direction -> RViz pose rotates left.
        #   STILL_THRESH: per-axis rate below which we call the robot "not rotating".
        #                 Rest noise is < ~0.2 deg/s; the slowest real Nav2 turn is
        #                 ~57 deg/s, so 0.8 deg/s cleanly separates the two.
        #   STILL_WIN   : samples of sustained quiet before we trust "still" and learn.
        #   BIAS_ALPHA  : EMA rate for stationary bias tracking (slow = chases thermal
        #                 drift, ignores noise; freezes automatically during real turns).
        #   BIAS_CLAMP  : hard cap so a tracked bias can never run away.
        #   DEADBAND    : after bias removal, |rate| below this -> exactly 0, so
        #                 residual/noise never integrates. 90x below a real turn.
        self.STILL_THRESH = 0.8     # deg/s
        self.STILL_WIN    = 50      # samples (~0.5 s @ 100 Hz)
        self.BIAS_ALPHA   = 0.002   # unitless EMA gain
        self.BIAS_CLAMP   = 5.0     # deg/s
        self.DEADBAND     = 0.6     # deg/s
        self.still_cnt    = 0

        self.pub = self.create_publisher(Imu, topic, 10)
        self.err = 0
        self.n = 0
        self.timer = self.create_timer(1.0 / rate, self.tick)
        self.get_logger().info("Publishing sensor_msgs/Imu on %s @ %.0f Hz (frame %s)"
                               % (topic, rate, self.frame_id))

    def _calibrate(self, n=300):
        sx = sy = sz = 0.0
        got = 0
        for _ in range(n):
            try:
                _, _, _, gx, gy, gz = self.dev.read()
                sx += gx; sy += gy; sz += gz; got += 1
            except Exception:
                pass
            time.sleep(0.005)
        if got == 0:
            return (0.0, 0.0, 0.0)
        return (sx / got, sy / got, sz / got)

    def tick(self):
        try:
            ax, ay, az, gx, gy, gz = self.dev.read()
        except Exception:
            self.err += 1
            if self.err % 50 == 1:
                self.get_logger().warn("I2C read errors: %d" % self.err)
            return
        # ---- bias-correct (deg/s) ----
        cgx = gx - self.bias[0]
        cgy = gy - self.bias[1]
        cgz = gz - self.bias[2]

        # ---- stationary detection: gyro reads ~0 on every axis when not turning ----
        if (abs(cgx) < self.STILL_THRESH and abs(cgy) < self.STILL_THRESH
                and abs(cgz) < self.STILL_THRESH):
            self.still_cnt += 1
        else:
            self.still_cnt = 0

        # ---- continuous bias tracking: chase slow thermal drift while still ----
        if self.still_cnt >= self.STILL_WIN:
            a = self.BIAS_ALPHA
            self.bias[0] = _clamp(self.bias[0] + a * (gx - self.bias[0]), self.BIAS_CLAMP)
            self.bias[1] = _clamp(self.bias[1] + a * (gy - self.bias[1]), self.BIAS_CLAMP)
            self.bias[2] = _clamp(self.bias[2] + a * (gz - self.bias[2]), self.BIAS_CLAMP)
            cgx = gx - self.bias[0]; cgy = gy - self.bias[1]; cgz = gz - self.bias[2]

        # ---- rate deadband: snap sub-threshold residual/noise to exactly 0 ----
        if abs(cgx) < self.DEADBAND: cgx = 0.0
        if abs(cgy) < self.DEADBAND: cgy = 0.0
        if abs(cgz) < self.DEADBAND: cgz = 0.0

        d2r = math.pi / 180.0

        m = Imu()
        m.header.stamp = self.get_clock().now().to_msg()
        m.header.frame_id = self.frame_id
        m.orientation.w = 1.0
        m.orientation_covariance[0] = -1.0  # no orientation estimate (REP-145)
        m.angular_velocity.x = cgx * d2r
        m.angular_velocity.y = cgy * d2r
        m.angular_velocity.z = cgz * d2r
        gcov = (0.02) ** 2
        m.angular_velocity_covariance[0] = gcov
        m.angular_velocity_covariance[4] = gcov
        m.angular_velocity_covariance[8] = gcov
        m.linear_acceleration.x = ax
        m.linear_acceleration.y = ay
        m.linear_acceleration.z = az
        acov = (0.1) ** 2
        m.linear_acceleration_covariance[0] = acov
        m.linear_acceleration_covariance[4] = acov
        m.linear_acceleration_covariance[8] = acov
        self.pub.publish(m)
        self.n += 1
        if self.n % 1500 == 0:   # ~every 15 s: let the user watch the bias track
            self.get_logger().info(
                "gyro bias est (deg/s): x=%.3f y=%.3f z=%.3f  still_cnt=%d"
                % (self.bias[0], self.bias[1], self.bias[2], self.still_cnt))

    def destroy_node(self):
        try:
            self.dev.close()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = ImuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
