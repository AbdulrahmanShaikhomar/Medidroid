"""
MediDroid Route Executor - LiDAR-Assisted Scripted Navigation
=============================================================

No Nav2, no AMCL, no map needed. Uses timed motor commands with
LiDAR distance checks for reliable scripted navigation.

Architecture:
  voice_listener ---> /voice_text ---> route_executor ---> /cmd_vel ---> safety_gate ---> ESP32
                                            |
                                       /scan (LiDAR feedback)

The robot can:
  - Drive forward for N seconds (timed)
  - Drive forward until front obstacle < X meters (LiDAR)
  - Turn left/right N degrees (calibrated timing)
  - Follow left/right wall at target distance (LiDAR P-controller)
  - Detect doorway openings on left/right side (LiDAR)
  - Pause automatically when obstacle detected, resume when clear
  - Speak status via TTS

All motor commands go through /cmd_vel -> safety_gate, which handles:
  - Obstacle avoidance (front/rear/side safety zones)
  - Motor compensation (RIGHT_SCALE, deadzone)
  - ESP32 serial communication
  - Watchdog timeout

LiDAR is mounted BACKWARD (yaw=pi from base_link):
  Robot front  = laser angles near +/-pi
  Robot rear   = laser angles near 0
  Robot left   = laser angles near -pi/2
  Robot right  = laser angles near +pi/2

CALIBRATION:
  ros2 run medidroid_base route_executor --ros-args -p mode:=calibrate

MANUAL TEST:
  ros2 topic pub --once /voice_text std_msgs/String "data: go to demo"

TEACHING A ROUTE:
  ros2 run medidroid_base teach_route
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
import threading
import time
import math
import subprocess


# ======================================================================
# CALIBRATION CONSTANTS - Measure on the actual robot!
#
# Run calibration mode:
#   ros2 run medidroid_base route_executor --ros-args -p mode:=calibrate
# ======================================================================

FORWARD_VEL = 0.10          # m/s cmd_vel linear.x for forward driving
SLOW_VEL = 0.06             # m/s for precise approach near walls
TURN_VEL = 1.2              # rad/s cmd_vel angular.z for rotation (STRONG - turns need power)
# Left and right turns are timed separately because the two motors are
# asymmetric (see RIGHT_SCALE in safety_gate). Calibrate each independently.
TIME_90_LEFT = 2.44         # seconds to rotate 90 deg LEFT at TURN_VEL (CALIBRATE!)
TIME_90_RIGHT = 2.4         # seconds to rotate 90 deg RIGHT at TURN_VEL (mirror of LEFT; CALIBRATE!)
TIME_90_DEG = 1.5           # legacy fallback (unused once L/R split is active)
RAMP_TIME = 0.3             # seconds to ramp up/down forward speed for smooth motion
# Real measured ground speed at FORWARD_VEL command (CALIBRATE via 'fwd_test'):
# drive fwd_test (forward_for 6.0s), measure distance D in meters, then
# CRUISE_SPEED_REAL = D / (6.0 - 0.75*RAMP_TIME).  Used by forward_dist.
CRUISE_SPEED_REAL = 0.225   # m/s actual ground speed (measured: 1.3m over 6.0s fwd_test)
# Straight-line yaw trim: robot drifts LEFT (right wheel faster), so apply a small
# steady RIGHT bias (negative angular.z = CW = right) during forward driving only.
# Does NOT affect turns. CALIBRATE: more negative = steers more right.
STRAIGHT_TRIM = -0.03       # rad/s yaw bias applied during forward_for / forward_until

# Wall following
WALL_KP = 1.5               # proportional gain for wall following correction
WALL_MAX_CORRECTION = 0.3   # max angular.z correction rad/s

# Doorway detection
WALL_NORMAL_MAX = 1.5       # meters - side distance above this = opening/doorway
DOOR_CONFIRM_TIME = 0.3     # seconds the opening must persist to confirm

# Safety - route executor pauses if obstacle is very close
# (safety_gate also has its own safety, this is an extra layer)
FRONT_SAFETY_DIST = 0.30    # pause route if front obstacle closer than this
OBSTACLE_CLEAR_DIST = 0.40  # resume when obstacle clears to this distance

# LiDAR arc sizes (radians)
FRONT_ARC = math.radians(60)   # +/-60 deg forward arc
REAR_ARC = math.radians(45)    # +/-45 deg rear arc
SIDE_ARC = math.radians(30)    # +/-30 deg side arcs centered at +/-90 from front


def speak(text, logger=None):
    """Text-to-speech via flite or espeak-ng (non-blocking)."""
    if logger:
        logger.info(f'[TTS] {text}')
    try:
        subprocess.Popen(['flite', '-t', text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        try:
            subprocess.Popen(['espeak-ng', '-s', '140', text],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            pass


class RouteExecutor(Node):
    def __init__(self):
        super().__init__('route_executor')

        # Parameters
        self.declare_parameter('mode', 'normal')
        self.mode = self.get_parameter('mode').get_parameter_value().string_value

        # LiDAR state (updated by _on_scan)
        self.front_dist = float('inf')
        self.rear_dist = float('inf')
        self.left_dist = float('inf')
        self.right_dist = float('inf')
        self.scan_ok = False

        # Route execution state
        self.is_running = False
        self.cancel_requested = False
        self.current_route_name = ''
        self.obstacle_paused = False

        # ROS interfaces
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.status_pub = self.create_publisher(String, '/medidroid_status', 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self._on_scan, 10)
        self.voice_sub = self.create_subscription(String, '/voice_text', self._on_voice, 10)

        # Load route definitions
        self.routes = ROUTES

        if self.mode == 'calibrate':
            self.get_logger().info('=== CALIBRATION MODE ===')
            threading.Thread(target=self._run_calibration, daemon=True).start()
        else:
            route_names = ', '.join(sorted(self.routes.keys()))
            self.get_logger().info(f'Route executor ready. Routes: {route_names}')
            speak('Route executor ready', self.get_logger())

    # ==================================================================
    # LiDAR Processing
    # ==================================================================

    def _on_scan(self, msg):
        """Convert raw laser scan into front/rear/left/right distances.

        LiDAR mounted backward (yaw=pi):
          laser angle 0     = robot REAR
          laser angle +/-pi = robot FRONT
          laser angle -pi/2 = robot LEFT
          laser angle +pi/2 = robot RIGHT
        """
        front = float('inf')
        rear = float('inf')
        left = float('inf')
        right = float('inf')

        angle = msg.angle_min
        for r in msg.ranges:
            if msg.range_min < r < msg.range_max:
                dist_from_front = math.pi - abs(angle)
                dist_from_rear = abs(angle)

                if dist_from_front <= FRONT_ARC:
                    front = min(front, r)

                if dist_from_rear <= REAR_ARC:
                    rear = min(rear, r)

                # Left side: laser angle near -pi/2
                if abs(angle - (-math.pi / 2)) <= SIDE_ARC:
                    left = min(left, r)

                # Right side: laser angle near +pi/2
                if abs(angle - (math.pi / 2)) <= SIDE_ARC:
                    right = min(right, r)

            angle += msg.angle_increment

        self.front_dist = front
        self.rear_dist = rear
        self.left_dist = left
        self.right_dist = right
        self.scan_ok = True

    # ==================================================================
    # Low-Level Movement
    # ==================================================================

    def _pub_vel(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_pub.publish(msg)

    def _full_stop(self):
        self._pub_vel(0.0, 0.0)

    def _check_obstacle(self):
        """Pause if front obstacle too close. Returns False if cancelled."""
        if self.front_dist >= FRONT_SAFETY_DIST:
            if self.obstacle_paused:
                self.obstacle_paused = False
                self.get_logger().info('Path clear - resuming')
            return True

        if not self.obstacle_paused:
            self.obstacle_paused = True
            self.get_logger().warn(f'Obstacle at {self.front_dist:.2f}m - pausing')
            speak('Obstacle detected. Waiting.', self.get_logger())
            self._full_stop()

        while self.front_dist < OBSTACLE_CLEAR_DIST:
            if self.cancel_requested:
                return False
            time.sleep(0.15)

        self.obstacle_paused = False
        self.get_logger().info('Obstacle cleared - resuming')
        return True

    def _ramp_factor(self, elapsed, total_duration):
        """Smooth ramp up at start and ramp down at end."""
        if elapsed < RAMP_TIME:
            return max(0.25, elapsed / RAMP_TIME)
        if total_duration - elapsed < RAMP_TIME:
            return max(0.25, (total_duration - elapsed) / RAMP_TIME)
        return 1.0

    # ==================================================================
    # Route Actions
    # ==================================================================

    def _act_forward_for(self, duration, speed=None):
        """Drive forward for N seconds."""
        speed = speed or FORWARD_VEL
        self.get_logger().info(f'  >> forward_for {duration:.1f}s at {speed:.2f} m/s')

        elapsed = 0.0
        dt = 0.05

        while elapsed < duration:
            if self.cancel_requested:
                self._full_stop()
                return False
            if not self._check_obstacle():
                return False

            factor = self._ramp_factor(elapsed, duration)
            self._pub_vel(speed * factor, STRAIGHT_TRIM)
            time.sleep(dt)
            elapsed += dt

        self._full_stop()
        time.sleep(0.1)
        return True

    def _act_forward_dist(self, meters, speed=None):
        """Drive forward an accurate DISTANCE (meters), open-loop.

        Converts distance -> duration using the measured CRUISE_SPEED_REAL and
        the ramp profile: a forward_for move covers
            cruise * (duration - 0.75*RAMP_TIME)
        so to travel `meters`:
            duration = meters / cruise + 0.75*RAMP_TIME
        """
        cruise = speed or CRUISE_SPEED_REAL
        if cruise <= 0:
            self.get_logger().error('  >> forward_dist: cruise speed <= 0')
            return False
        duration = (meters / cruise) + 0.75 * RAMP_TIME
        # forward_for needs duration >= 2*RAMP_TIME for the ramp model to hold
        duration = max(duration, 2.0 * RAMP_TIME)
        self.get_logger().info(
            f'  >> forward_dist {meters:.2f}m -> {duration:.2f}s '
            f'(cruise={cruise:.3f} m/s)'
        )
        return self._act_forward_for(duration, FORWARD_VEL)

    def _act_forward_until(self, target_dist, speed=None, timeout=30.0):
        """Drive forward until front obstacle < target_dist meters."""
        speed = speed or FORWARD_VEL
        self.get_logger().info(f'  >> forward_until front < {target_dist:.2f}m')

        if not self.scan_ok:
            self.get_logger().warn('No LiDAR data! Falling back to 3s forward')
            return self._act_forward_for(3.0, speed)

        elapsed = 0.0
        dt = 0.05
        approach_zone = target_dist + 0.20  # slow down in last 20cm

        while elapsed < timeout:
            if self.cancel_requested:
                self._full_stop()
                return False

            if self.front_dist <= target_dist:
                self.get_logger().info(f'  -> reached {self.front_dist:.2f}m from wall')
                self._full_stop()
                time.sleep(0.1)
                return True

            # Slow down on approach
            v = SLOW_VEL if self.front_dist < approach_zone else speed

            # Ramp up at start
            if elapsed < RAMP_TIME:
                v *= max(0.25, elapsed / RAMP_TIME)

            self._pub_vel(v, STRAIGHT_TRIM)
            time.sleep(dt)
            elapsed += dt

        self.get_logger().warn('  -> forward_until timeout!')
        self._full_stop()
        return True

    def _act_turn(self, degrees, direction):
        """Turn N degrees left or right using calibrated timing.

        Turns use FULL power the whole time (no ramp) - in-place rotation
        needs to punch through static friction or the wheels won't move.
        """
        time_90 = TIME_90_LEFT if direction == 'left' else TIME_90_RIGHT
        time_per_deg = time_90 / 90.0
        duration = abs(degrees) * time_per_deg
        w = TURN_VEL if direction == 'left' else -TURN_VEL

        self.get_logger().info(f'  >> turn_{direction} {degrees} deg ({duration:.2f}s) at w={w:.2f}')

        # Brief pause before turning for clean start
        self._full_stop()
        time.sleep(0.15)

        elapsed = 0.0
        dt = 0.05

        while elapsed < duration:
            if self.cancel_requested:
                self._full_stop()
                return False

            # FULL power throughout - no ramp. Turns must be forceful.
            self._pub_vel(0.0, w)
            time.sleep(dt)
            elapsed += dt

        self._full_stop()
        time.sleep(0.30)  # settle after turn (let momentum die)
        return True

    def _act_wall_follow(self, side, target_dist, duration, speed=None):
        """Follow a wall at target_dist for duration seconds.
        Uses a P-controller on LiDAR side distance.
        """
        speed = speed or FORWARD_VEL
        self.get_logger().info(
            f'  >> wall_follow_{side} at {target_dist:.2f}m for {duration:.1f}s'
        )

        if not self.scan_ok:
            self.get_logger().warn('No LiDAR - driving straight')
            return self._act_forward_for(duration, speed)

        elapsed = 0.0
        dt = 0.05

        while elapsed < duration:
            if self.cancel_requested:
                self._full_stop()
                return False
            if not self._check_obstacle():
                return False

            wall_dist = self.left_dist if side == 'left' else self.right_dist

            correction = 0.0
            if wall_dist < 8.0:  # valid reading
                error = target_dist - wall_dist
                # Left wall: positive error = too far = steer left (+angular.z)
                # Right wall: positive error = too far = steer right (-angular.z)
                if side == 'left':
                    correction = WALL_KP * error
                else:
                    correction = -WALL_KP * error
                correction = max(-WALL_MAX_CORRECTION, min(WALL_MAX_CORRECTION, correction))

            self._pub_vel(speed, correction)
            time.sleep(dt)
            elapsed += dt

        self._full_stop()
        time.sleep(0.1)
        return True

    def _act_detect_door(self, side, speed=None, timeout=30.0):
        """Drive forward until a doorway opening appears on the given side.
        Detects when side distance jumps from < WALL_NORMAL_MAX to > WALL_NORMAL_MAX.
        """
        speed = speed or FORWARD_VEL
        self.get_logger().info(f'  >> detect_door_{side}')

        if not self.scan_ok:
            self.get_logger().warn('No LiDAR - driving 2s forward')
            return self._act_forward_for(2.0, speed)

        baseline = self.left_dist if side == 'left' else self.right_dist
        if baseline > WALL_NORMAL_MAX:
            self.get_logger().warn(f'  No wall on {side} ({baseline:.2f}m) - driving 2s')
            return self._act_forward_for(2.0, speed)

        self.get_logger().info(f'  Baseline {side} wall: {baseline:.2f}m')

        elapsed = 0.0
        opening_timer = 0.0
        dt = 0.05

        while elapsed < timeout:
            if self.cancel_requested:
                self._full_stop()
                return False
            if not self._check_obstacle():
                return False

            dist = self.left_dist if side == 'left' else self.right_dist

            if dist > WALL_NORMAL_MAX:
                opening_timer += dt
                if opening_timer >= DOOR_CONFIRM_TIME:
                    self.get_logger().info(f'  -> Door on {side} at {dist:.2f}m!')
                    # Drive a bit more to center on the opening
                    self._pub_vel(SLOW_VEL, 0.0)
                    time.sleep(0.4)
                    self._full_stop()
                    return True
            else:
                opening_timer = 0.0

            self._pub_vel(speed, 0.0)
            time.sleep(dt)
            elapsed += dt

        self.get_logger().warn('  -> timeout, no door found')
        self._full_stop()
        return True

    def _act_backward_for(self, duration, speed=None):
        """Reverse for N seconds."""
        speed = speed or FORWARD_VEL
        self.get_logger().info(f'  >> backward_for {duration:.1f}s')

        elapsed = 0.0
        dt = 0.05
        while elapsed < duration:
            if self.cancel_requested:
                self._full_stop()
                return False
            self._pub_vel(-speed, 0.0)
            time.sleep(dt)
            elapsed += dt

        self._full_stop()
        time.sleep(0.1)
        return True

    def _act_wait(self, duration):
        """Pause for N seconds."""
        self.get_logger().info(f'  >> wait {duration:.1f}s')
        elapsed = 0.0
        while elapsed < duration:
            if self.cancel_requested:
                return False
            time.sleep(0.1)
            elapsed += 0.1
        return True

    def _act_announce(self, text):
        """Speak text."""
        speak(text, self.get_logger())
        return True

    # ==================================================================
    # Step Dispatcher
    # ==================================================================

    def _run_step(self, step):
        """Execute one route step dict."""
        action = step.get('action', '')

        if action == 'forward_for':
            return self._act_forward_for(step.get('duration', 2.0), step.get('speed'))
        elif action == 'forward_dist':
            return self._act_forward_dist(step.get('meters', 1.0), step.get('speed'))
        elif action == 'forward_until':
            return self._act_forward_until(step.get('distance', 0.5), step.get('speed'))
        elif action == 'turn_left':
            return self._act_turn(step.get('degrees', 90), 'left')
        elif action == 'turn_right':
            return self._act_turn(step.get('degrees', 90), 'right')
        elif action == 'wall_follow_left':
            return self._act_wall_follow('left', step.get('distance', 0.4),
                                         step.get('duration', 5.0), step.get('speed'))
        elif action == 'wall_follow_right':
            return self._act_wall_follow('right', step.get('distance', 0.4),
                                         step.get('duration', 5.0), step.get('speed'))
        elif action == 'detect_door_left':
            return self._act_detect_door('left', step.get('speed'))
        elif action == 'detect_door_right':
            return self._act_detect_door('right', step.get('speed'))
        elif action == 'backward_for':
            return self._act_backward_for(step.get('duration', 1.0), step.get('speed'))
        elif action == 'wait':
            return self._act_wait(step.get('duration', 1.0))
        elif action == 'announce':
            return self._act_announce(step.get('text', ''))
        elif action == 'stop':
            self._full_stop()
            return True
        else:
            self.get_logger().warn(f'Unknown action: {action}')
            return True

    # ==================================================================
    # Route Execution
    # ==================================================================

    def _execute_route(self, route_key):
        """Run a full route by key name."""
        if route_key not in self.routes:
            speak(f'Unknown route {route_key}', self.get_logger())
            return

        route = self.routes[route_key]
        steps = route.get('steps', [])
        label = route.get('display_name', route_key)

        self.is_running = True
        self.cancel_requested = False
        self.current_route_name = route_key

        speak(f'Going to {label}', self.get_logger())
        self.get_logger().info(f'Route "{route_key}" -> {len(steps)} steps')
        self._pub_status(f'navigating:{label}')

        # Execute forward steps
        for i, step in enumerate(steps):
            self.get_logger().info(f'Step {i+1}/{len(steps)}:')
            if not self._run_step(step):
                self.get_logger().info('Route CANCELLED')
                self._full_stop()
                speak('Navigation cancelled', self.get_logger())
                self._pub_status('stopped')
                self.is_running = False
                return

        speak(f'Arrived at {label}', self.get_logger())
        self._pub_status(f'arrived:{label}')

        # Wait at destination
        wait_time = route.get('wait_time', 5.0)
        if wait_time > 0 and not self.cancel_requested:
            speak(f'Waiting {int(wait_time)} seconds', self.get_logger())
            self._pub_status(f'waiting:{label}')
            self._act_wait(wait_time)

        # Return home if return_steps defined
        if 'return_steps' in route and not self.cancel_requested:
            ret_steps = route['return_steps']
            speak('Returning home', self.get_logger())
            self._pub_status('returning:HOME')

            for i, step in enumerate(ret_steps):
                self.get_logger().info(f'Return {i+1}/{len(ret_steps)}:')
                if not self._run_step(step):
                    self._full_stop()
                    self._pub_status('stopped')
                    self.is_running = False
                    return

            speak('I am back home', self.get_logger())
            self._pub_status('ready')

        self.is_running = False

    def _pub_status(self, status):
        msg = String()
        msg.data = status
        self.status_pub.publish(msg)

    # ==================================================================
    # Voice Command Handler
    # ==================================================================

    def _on_voice(self, msg):
        text = msg.data.strip().lower()
        if not text:
            return

        self.get_logger().info(f'Voice: "{text}"')

        # -- Stop --
        if text in ('stop', 'cancel', 'halt', 'abort', 'freeze'):
            if self.is_running:
                self.cancel_requested = True
                self._full_stop()
                speak('Stopping', self.get_logger())
            else:
                speak('I am not moving', self.get_logger())
            return

        # -- List routes --
        if text in ('list', 'list destinations', 'where can you go', 'help'):
            names = [self.routes[k].get('display_name', k)
                     for k in sorted(self.routes.keys())]
            speak(f'I can go to: {", ".join(names)}', self.get_logger())
            return

        # -- Strip navigation prefixes --
        target = text
        for prefix in ('go to the ', 'go to ', 'navigate to the ', 'navigate to ',
                        'take me to the ', 'take me to ', 'drive to the ', 'drive to ',
                        'head to the ', 'head to ', 'move to the ', 'move to '):
            if target.startswith(prefix):
                target = target[len(prefix):]
                break

        # -- Resolve route --
        route_key = self._match_route(target)

        if route_key:
            if self.is_running:
                self.cancel_requested = True
                self._full_stop()
                time.sleep(0.3)
            threading.Thread(
                target=self._execute_route, args=(route_key,), daemon=True
            ).start()
        else:
            speak(f'I do not know where {target} is', self.get_logger())
            self.get_logger().warn(f'No route for: "{target}"')

    def _match_route(self, target):
        """Match spoken target to a route key."""
        target = target.strip()

        # Direct key match
        if target in self.routes:
            return target

        # Match by display_name (case insensitive)
        for key, route in self.routes.items():
            if route.get('display_name', '').lower() == target:
                return key

        # Partial match in display_name or key
        for key, route in self.routes.items():
            dn = route.get('display_name', '').lower()
            if target in dn or target in key:
                return key

        # Alias match
        for key, route in self.routes.items():
            for alias in route.get('aliases', []):
                if target == alias.lower() or alias.lower() in target:
                    return key

        return None

    # ==================================================================
    # Calibration Mode
    # ==================================================================

    def _run_calibration(self):
        """Interactive calibration to find FORWARD_VEL and TIME_90_DEG."""
        time.sleep(2.0)

        self.get_logger().info('=' * 50)
        self.get_logger().info('CALIBRATION MODE')
        self.get_logger().info('=' * 50)
        speak('Starting calibration', self.get_logger())

        # Wait for LiDAR
        if not self.scan_ok:
            self.get_logger().info('Waiting for LiDAR...')
            for _ in range(100):
                if self.scan_ok:
                    break
                time.sleep(0.1)

        # --- Test 1: Forward speed ---
        self.get_logger().info('')
        self.get_logger().info('TEST 1: FORWARD SPEED')
        self.get_logger().info(f'  Will drive forward 3 seconds at linear.x={FORWARD_VEL}')
        self.get_logger().info('  MEASURE the distance traveled!')
        speak('Test 1. Forward speed. Starting in 3 seconds.', self.get_logger())
        time.sleep(3.0)

        speak('Go', self.get_logger())
        front_before = self.front_dist
        self._act_forward_for(3.0, FORWARD_VEL)
        front_after = self.front_dist

        if front_before < 8.0 and front_after < 8.0:
            lidar_dist = front_before - front_after
            self.get_logger().info(f'  LiDAR measured: ~{lidar_dist:.3f}m in 3s = {lidar_dist/3:.3f} m/s')
        self.get_logger().info('  Measure actual distance. Speed = distance / 3')
        speak('Test 1 done. Measure distance.', self.get_logger())
        time.sleep(5.0)

        # --- Test 2: 90-degree turn ---
        self.get_logger().info('')
        self.get_logger().info(f'TEST 2: 90-DEGREE TURN (TIME_90_DEG = {TIME_90_DEG}s)')
        self.get_logger().info('  Robot will attempt a 90 degree left turn')
        speak('Test 2. Ninety degree turn in 3 seconds.', self.get_logger())
        time.sleep(3.0)

        speak('Turning', self.get_logger())
        self._act_turn(90, 'left')

        self.get_logger().info('  Did it turn exactly 90 degrees?')
        self.get_logger().info(f'  Over-rotated -> increase TIME_90_DEG above {TIME_90_DEG}')
        self.get_logger().info(f'  Under-rotated -> decrease TIME_90_DEG below {TIME_90_DEG}')
        speak('Test 2 done. Check the angle.', self.get_logger())
        time.sleep(5.0)

        # --- Test 3: Forward until wall ---
        if self.scan_ok:
            self.get_logger().info('')
            self.get_logger().info('TEST 3: FORWARD UNTIL WALL (target 0.5m)')
            self.get_logger().info(f'  Front distance now: {self.front_dist:.2f}m')
            speak('Test 3. Driving toward wall. Will stop at half meter.', self.get_logger())
            time.sleep(2.0)

            self._act_forward_until(0.5)
            self.get_logger().info(f'  Stopped at {self.front_dist:.2f}m')
            speak(f'Stopped at {self.front_dist:.1f} meters', self.get_logger())

        self.get_logger().info('')
        self.get_logger().info('=' * 50)
        self.get_logger().info('CALIBRATION COMPLETE')
        self.get_logger().info(f'  Update FORWARD_VEL (currently {FORWARD_VEL})')
        self.get_logger().info(f'  Update TIME_90_DEG (currently {TIME_90_DEG})')
        self.get_logger().info('=' * 50)
        speak('Calibration complete', self.get_logger())


# ======================================================================
# ROUTE DEFINITIONS
#
# Each route has:
#   display_name  - friendly name for TTS and matching
#   aliases       - list of alternative spoken names
#   wait_time     - seconds to wait at destination (default 5)
#   steps         - list of action dicts (executed in order)
#   return_steps  - (optional) steps to go back home
#
# Available actions:
#   {action: forward_for,      duration: 3.0, speed: 0.10}
#   {action: forward_until,    distance: 0.5, speed: 0.10}
#   {action: turn_left,        degrees: 90}
#   {action: turn_right,       degrees: 90}
#   {action: wall_follow_left, distance: 0.4, duration: 5.0}
#   {action: wall_follow_right,distance: 0.4, duration: 5.0}
#   {action: detect_door_left}
#   {action: detect_door_right}
#   {action: backward_for,     duration: 1.0}
#   {action: wait,             duration: 1.0}
#   {action: announce,         text: "hello"}
#   {action: stop}
#
# HOW TO CREATE A ROUTE:
#   1. Calibrate the robot (mode:=calibrate)
#   2. Run teach_route to record movements interactively
#   3. Copy the output into this ROUTES dict
#   4. Test and refine
# ======================================================================

ROUTES = {

    # --- Built-in test routes ---

    'room_101': {
        'display_name': 'Doctor Abadi Room',
        'aliases': ['room 101', 'room one oh one', 'doctor abadi', 'doctor abadi room',
                    'abadi room', 'one oh one'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Heading to Doctor Abadi room'},
            {'action': 'forward_dist', 'meters': 2.6},
            {'action': 'turn_left', 'degrees': 90},
            {'action': 'forward_dist', 'meters': 2.8},
            {'action': 'turn_left', 'degrees': 90},
            {'action': 'forward_dist', 'meters': 1.0},
            {'action': 'announce', 'text': 'Arriving at Doctor Abadi room'},
            {'action': 'stop'},
        ],
    },

    'demo': {
        'display_name': 'Demo',
        'aliases': ['demo square', 'square'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Running demo pattern'},
            {'action': 'forward_for', 'duration': 2.0},
            {'action': 'turn_left', 'degrees': 90},
            {'action': 'forward_for', 'duration': 2.0},
            {'action': 'turn_left', 'degrees': 90},
            {'action': 'forward_for', 'duration': 2.0},
            {'action': 'turn_left', 'degrees': 90},
            {'action': 'forward_for', 'duration': 2.0},
            {'action': 'turn_left', 'degrees': 90},
            {'action': 'announce', 'text': 'Demo complete'},
            {'action': 'stop'},
        ],
    },

    'fwd_test': {
        'display_name': 'Forward Speed Test',
        'aliases': ['forward test', 'fwd test', 'speed test', 'forward'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Driving forward for six seconds'},
            {'action': 'forward_for', 'duration': 6.0},
            {'action': 'announce', 'text': 'Measure the distance now'},
            {'action': 'stop'},
        ],
    },

    'dist_test': {
        'display_name': 'Distance Test',
        'aliases': ['distance test', 'one meter', 'drive one meter'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Driving forward one meter'},
            {'action': 'forward_dist', 'meters': 1.0},
            {'action': 'announce', 'text': 'One meter complete'},
            {'action': 'stop'},
        ],
    },

    'straight_test': {
        'display_name': 'Straight Test',
        'aliases': ['straight test', 'straight', 'two meter', 'two meters'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Driving straight two meters'},
            {'action': 'forward_dist', 'meters': 2.0},
            {'action': 'announce', 'text': 'Two meters complete'},
            {'action': 'stop'},
        ],
    },

    'obstacle_test': {
        'display_name': 'Obstacle Test',
        'aliases': ['obstacle test', 'test obstacle', 'obstacle'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Driving forward three meters. Step in front to test stopping.'},
            {'action': 'forward_dist', 'meters': 3.0},
            {'action': 'announce', 'text': 'Obstacle test complete'},
            {'action': 'stop'},
        ],
    },

    'right_test': {
        'display_name': 'Right Turn Test',
        'aliases': ['right test', 'test right', 'right turn'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Testing right turn'},
            {'action': 'turn_right', 'degrees': 90},
            {'action': 'announce', 'text': 'Right turn complete'},
            {'action': 'stop'},
        ],
    },

    'left_test': {
        'display_name': 'Left Turn Test',
        'aliases': ['left test', 'test left', 'left turn'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Testing left turn'},
            {'action': 'turn_left', 'degrees': 90},
            {'action': 'announce', 'text': 'Left turn complete'},
            {'action': 'stop'},
        ],
    },

    'wall_test': {
        'display_name': 'Wall Test',
        'aliases': ['wall follow', 'wall'],
        'wait_time': 2,
        'steps': [
            {'action': 'announce', 'text': 'Following left wall'},
            {'action': 'wall_follow_left', 'distance': 0.4, 'duration': 5.0},
            {'action': 'announce', 'text': 'Approaching wall'},
            {'action': 'forward_until', 'distance': 0.5},
            {'action': 'announce', 'text': 'Wall test complete'},
            {'action': 'stop'},
        ],
    },

    # ================================================================
    #  HOSPITAL ROUTES - Fill these in after calibration!
    #
    #  Use teach_route to record each path, then paste here.
    # ================================================================

    # 'cardiology': {
    #     'display_name': 'Cardiology',
    #     'aliases': ['cardio', 'heart', 'cardiac'],
    #     'wait_time': 10,
    #     'steps': [
    #         {'action': 'announce', 'text': 'Heading to Cardiology'},
    #         {'action': 'forward_for', 'duration': 3.0},
    #         {'action': 'turn_left', 'degrees': 90},
    #         {'action': 'wall_follow_left', 'distance': 0.4, 'duration': 5.0},
    #         {'action': 'detect_door_right'},
    #         {'action': 'turn_right', 'degrees': 90},
    #         {'action': 'forward_until', 'distance': 0.8},
    #         {'action': 'announce', 'text': 'Arrived at Cardiology'},
    #         {'action': 'stop'},
    #     ],
    #     'return_steps': [
    #         {'action': 'announce', 'text': 'Returning home'},
    #         {'action': 'backward_for', 'duration': 1.0},
    #         {'action': 'turn_left', 'degrees': 90},
    #         {'action': 'wall_follow_right', 'distance': 0.4, 'duration': 5.0},
    #         {'action': 'turn_right', 'degrees': 90},
    #         {'action': 'forward_until', 'distance': 0.5},
    #         {'action': 'announce', 'text': 'Back home'},
    #         {'action': 'stop'},
    #     ],
    # },
    #
    # 'room_101': {
    #     'display_name': 'Room 101',
    #     'aliases': ['doctor tariq', 'tariq', 'one oh one'],
    #     'wait_time': 10,
    #     'steps': [
    #         {'action': 'announce', 'text': 'Heading to Room 101'},
    #         # ... fill in after teaching ...
    #         {'action': 'stop'},
    #     ],
    # },
}


def main():
    rclpy.init()
    node = RouteExecutor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._full_stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
