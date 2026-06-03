import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
import serial
import threading
import time
import math

# ── Robot physical parameters ──
WHEEL_BASE = 0.34        # meters between left and right wheels
MAX_VEL = 0.20           # m/s — what the robot does at MAX_PWM
MAX_PWM = 150            # absolute max PWM sent to ESP32
MIN_PWM = 55             # motors stall below this — tested minimum
RIGHT_SCALE = 0.82       # right motor runs FASTER — scale it down so the robot
                         # drives straight. Matches webdrive RBAL=0.82, the
                         # hand-verified teleop calibration the user trusts.

# ── LiDAR safety zones (meters) ──
# LiDAR is mounted BACKWARD (yaw=pi): laser angle 0 = robot rear, ±pi = robot front
FRONT_STOP_DIST = 0.30   # hard stop — too close ahead
FRONT_SLOW_DIST = 0.60   # reduce to 50% speed ahead
REAR_STOP_DIST = 0.25    # hard stop — too close behind (for reverse)
SIDE_SLOW_DIST = 0.25    # reduce speed when walls are close on sides

# Arc definitions (radians from robot's perspective, mapped to laser frame)
FRONT_ARC = 1.047        # ±60° forward  → laser angles near ±pi
REAR_ARC = 0.785         # ±45° backward → laser angles near 0
SIDE_ARC_MIN = 1.047     # side zone starts at 60° from front
SIDE_ARC_MAX = 1.571     # side zone ends at 90° from front (pure sideways)

# ── In-place rotation (FAITHFUL PASSTHROUGH, Nav2/IMU in control) ──
# HISTORY: this gate used to run its own pivot state machine — a breakaway KICK, then
# ON/OFF PULSES, a 0.3 s pivot-watchdog that stopped between bursts, and a "reversal
# dwell" that blocked the opposite turn direction for 0.5 s after a pivot ended. That
# machinery WAS the "turn then cancel" the robot showed: every pivot was drive->M,0,0->
# drive->M,0,0, and the reversal lock pinned it to whichever direction fired first (so it
# "kept turning left" and refused the right correction). That is the gate overriding Nav2.
# 2026-06-03 FIX: rip all of it out. Nav2's controller already closes the heading loop on
# the IMU (alpha1/alpha2~0 in AMCL), so it alone decides direction and when to stop. The
# gate now just translates the LATEST (v,w) into wheel PWM every frame, continuously — no
# pulsing, no watchdog stop-between-bursts, no reversal lock. The ONLY thing the gate adds
# is a breakaway PWM floor for in-place turns, because a 4-wheel skid-steer pivot needs
# ~140 PWM to break static friction and Nav2's gentle |w|~0.1 maps to ~13 PWM (it would
# just whine). When Nav2 drops |w| below TURN_W_MIN the gate stops turning immediately.
TURN_V_MAX   = 0.03   # |linear.x| below this  -> treat as an in-place pivot (else mixed drive)
TURN_W_MIN   = 0.06   # |angular.z| below this (when ~stationary) -> hold still (M,0,0). Just a
                      # small chatter guard; NOT a direction filter. Nav2 decides the turn.
# A 4-wheel skid-steer in-place pivot scrubs all four tyres sideways, so its breakaway
# static friction is HIGH. The validated webdrive spin used 150/110 (raw/scaled) and a hand
# pivot worked at 130/106; the base did NOT rotate at 123/100. So any commanded pivot is
# floored into the proven 140-150 band, scaled by |w|, sign = Nav2's sign. Continuous.
TURN_PWM_MIN = 140    # raw PWM floor for a pivot (proven turn band starts ~140)
TURN_PWM_MAX = 150    # raw PWM ceiling for a pivot (== MAX_PWM)
TURN_W_REF   = 0.5    # |w| (rad/s) that maps to TURN_PWM_MAX; RPP rarely exceeds this.


class DiffDriveBridge(Node):
    def __init__(self):
        super().__init__('safety_gate')
        self.ser = None
        try:
            self.ser = serial.Serial('/dev/ttyESP32', 115200, timeout=0.05)
            self.get_logger().info('ESP32 connected on /dev/ttyESP32')
        except Exception as e:
            self.get_logger().error(f'ESP32 not found: {e}')

        # Safety state
        self.front_blocked = False
        self.front_slow = False
        self.rear_blocked = False
        self.side_slow = False
        self.closest_front = float('inf')
        self.closest_rear = float('inf')
        self.closest_side = float('inf')

        # Watchdog: stop motors if no cmd_vel for 0.5s
        self.last_cmd_time = time.time()
        self.watchdog_timer = self.create_timer(0.25, self._watchdog)

        self.cmd_sub = self.create_subscription(Twist, '/cmd_vel', self._on_cmd, 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self._on_scan, 10)

        if self.ser:
            self.drain_thread = threading.Thread(target=self._drain_serial, daemon=True)
            self.drain_thread.start()

        self.get_logger().info('safety_gate ready — proportional diff-drive with 360° safety')

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _drain_serial(self):
        """Drain ESP32 serial buffer to prevent buildup."""
        while rclpy.ok():
            try:
                if self.ser and self.ser.in_waiting:
                    self.ser.read(self.ser.in_waiting)
                else:
                    time.sleep(0.05)
            except Exception:
                time.sleep(0.1)

    def _watchdog(self):
        """Stop motors if no cmd_vel for 0.5s."""
        if self.ser and (time.time() - self.last_cmd_time) > 0.5:
            self.ser.write(b'M,0,0\n')

    def stop_motors(self, repeat=5):
        """Force a hard stop. Sent repeatedly on shutdown because the ESP32
        firmware watchdog is disabled — if this node dies mid-turn without it,
        the last full-power command stays latched and the robot runs away."""
        if not self.ser:
            return
        for _ in range(repeat):
            try:
                self.ser.write(b'M,0,0\n')
                time.sleep(0.02)
            except Exception:
                break

    def _send(self, pwm_l, pwm_r):
        """Send motor command with right-motor compensation and deadzone."""
        # Apply right motor compensation
        pwm_r = int(pwm_r * RIGHT_SCALE)

        # Deadzone: if commanded but too low, bump up or zero out
        if 0 < abs(pwm_l) < MIN_PWM:
            pwm_l = MIN_PWM * (1 if pwm_l > 0 else -1)
        if 0 < abs(pwm_r) < MIN_PWM:
            pwm_r = MIN_PWM * (1 if pwm_r > 0 else -1)

        # Clamp
        pwm_l = max(-MAX_PWM, min(MAX_PWM, pwm_l))
        pwm_r = max(-MAX_PWM, min(MAX_PWM, pwm_r))

        cmd = f'M,{pwm_l},{pwm_r}\n'
        if self.ser:
            self.ser.write(cmd.encode())
        return cmd.strip()

    def _vel_to_pwm(self, vel_ms):
        """Convert m/s to raw PWM (before RIGHT_SCALE, before deadzone)."""
        if abs(vel_ms) < 0.005:
            return 0
        return int((vel_ms / MAX_VEL) * MAX_PWM)

    # ── LiDAR 360° safety scan ───────────────────────────────────────────────

    def _on_scan(self, msg):
        """Scan ALL directions for obstacles.
        LiDAR mounted backward (yaw=pi):
          robot front  = laser angle near ±pi
          robot rear   = laser angle near 0
          robot sides  = laser angle near ±pi/2
        """
        closest_front = float('inf')
        closest_rear = float('inf')
        closest_side = float('inf')
        angle = msg.angle_min

        for r in msg.ranges:
            if msg.range_min < r < msg.range_max:
                # How far is this angle from ±pi (robot front)?
                dist_from_front = math.pi - abs(angle)
                # How far is this angle from 0 (robot rear)?
                dist_from_rear = abs(angle)

                # Front arc: within FRONT_ARC of ±pi
                if dist_from_front <= FRONT_ARC:
                    if r < closest_front:
                        closest_front = r

                # Rear arc: within REAR_ARC of 0
                if dist_from_rear <= REAR_ARC:
                    if r < closest_rear:
                        closest_rear = r

                # Side arcs: between 60° and 90° from front on each side
                if SIDE_ARC_MIN <= dist_from_front <= SIDE_ARC_MAX:
                    if r < closest_side:
                        closest_side = r

            angle += msg.angle_increment

        self.closest_front = closest_front
        self.closest_rear = closest_rear
        self.closest_side = closest_side

        # Front safety
        self.front_blocked = closest_front < FRONT_STOP_DIST
        self.front_slow = FRONT_STOP_DIST <= closest_front < FRONT_SLOW_DIST

        # Rear safety
        self.rear_blocked = closest_rear < REAR_STOP_DIST

        # Side safety (slow down in narrow spaces)
        self.side_slow = closest_side < SIDE_SLOW_DIST

        # Log transitions only (not every scan)
        prev_fb = getattr(self, '_prev_front_blocked', False)
        prev_rb = getattr(self, '_prev_rear_blocked', False)
        if self.front_blocked and not prev_fb:
            self.get_logger().warn(f'FRONT BLOCKED at {closest_front:.2f}m — stopping forward')
        elif not self.front_blocked and prev_fb:
            self.get_logger().info('Front clear — resuming')
        if self.rear_blocked and not prev_rb:
            self.get_logger().warn(f'REAR BLOCKED at {closest_rear:.2f}m — stopping reverse')
        elif not self.rear_blocked and prev_rb:
            self.get_logger().info('Rear clear — resuming')
        self._prev_front_blocked = self.front_blocked
        self._prev_rear_blocked = self.rear_blocked

    # ── Velocity command handler ──────────────────────────────────────────────

    def _on_cmd(self, msg):
        if not self.ser:
            return
        self.last_cmd_time = time.time()

        try:
            v = msg.linear.x    # m/s forward(+) / backward(-)
            # Standard ROS convention: positive angular.z = LEFT (CCW),
            # negative = RIGHT (CW). The earlier w-negation was a mis-fix made
            # during the demo-square phase (a 4-turn square hides direction);
            # a single right_test turn proved it inverted, so it's removed.
            w = msg.angular.z   # rad/s left(+) / right(-)

            # ── In-place pivot: faithful, CONTINUOUS, Nav2-signed ──
            # |v| small + a real turn asked: rotate in the EXACT direction Nav2 commands,
            # at a PWM floored into the proven breakaway band and scaled by |w|. No pulsing,
            # no reversal lock — drive it every frame, and the moment Nav2 drops |w| below
            # TURN_W_MIN we fall into the deadband below and stop. Nav2 owns when/where.
            if abs(v) < TURN_V_MAX:
                if abs(w) < TURN_W_MIN:
                    self.ser.write(b'M,0,0\n')   # not really turning -> hold still
                    return
                frac = min(1.0, (abs(w) - TURN_W_MIN) / max(1e-6, TURN_W_REF - TURN_W_MIN))
                turn_pwm = int(TURN_PWM_MIN + (TURN_PWM_MAX - TURN_PWM_MIN) * frac)
                if w > 0:        # CCW / LEFT
                    cmd = self._send(-turn_pwm, turn_pwm)
                else:            # CW / RIGHT
                    cmd = self._send(turn_pwm, -turn_pwm)
                self.get_logger().info(f'TURN w={w:+.2f} pwm={turn_pwm} -> {cmd}')
                return

            # ── Safety overrides ──

            # Front blocked: stop forward, allow backward and turning
            if self.front_blocked and v > 0:
                v = 0.0
                # If also not turning, just stop
                if abs(w) < 0.1:
                    self.ser.write(b'M,0,0\n')
                    return

            # Rear blocked: stop backward, allow forward and turning
            if self.rear_blocked and v < 0:
                v = 0.0
                if abs(w) < 0.1:
                    self.ser.write(b'M,0,0\n')
                    return

            # Front slow zone: reduce forward speed to 50%
            if self.front_slow and v > 0:
                v *= 0.5
                w *= 0.7  # slightly reduce turn speed too

            # Side slow zone (narrow hallway): reduce overall speed to 60%
            if self.side_slow:
                v *= 0.6
                w *= 0.6

            # ── Differential drive kinematics ──
            # v_left  = v - w * (wheelbase / 2)
            # v_right = v + w * (wheelbase / 2)
            v_left = v - w * (WHEEL_BASE / 2.0)
            v_right = v + w * (WHEEL_BASE / 2.0)

            # Convert to PWM (raw, before RIGHT_SCALE)
            pwm_l = self._vel_to_pwm(v_left)
            pwm_r = self._vel_to_pwm(v_right)

            # Send with compensation and deadzone
            cmd = self._send(pwm_l, pwm_r)

            self.get_logger().info(
                f'v={v:.2f} w={w:.2f} L={v_left:.2f} R={v_right:.2f} '
                f'F={self.closest_front:.2f} R={self.closest_rear:.2f} S={self.closest_side:.2f} '
                f'-> {cmd}'
            )
        except Exception as e:
            self.get_logger().error(f'cmd error: {e}')


def main():
    rclpy.init()
    node = DiffDriveBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        # Ctrl-C or an external SIGTERM (e.g. `ros2 launch` teardown) — both are
        # normal ways to stop the gate, so exit quietly. The finally below still
        # runs the hard-stop, so the wheels are never left latched.
        pass
    finally:
        # Force a stop on the way out so a Ctrl-C mid-turn can't leave the
        # ESP32 latched on a full-power command (the runaway we hit).
        node.stop_motors()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
