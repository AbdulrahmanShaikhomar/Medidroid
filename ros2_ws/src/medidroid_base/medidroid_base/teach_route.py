"""
MediDroid Route Teacher
=======================

Drive the robot manually using keyboard and record the movements.
When done, it prints a route definition you can paste into route_executor.py.

Usage:
  ros2 run medidroid_base teach_route

Controls:
  W  = drive forward (hold or tap to toggle)
  S  = drive backward
  A  = turn left
  D  = turn right
  SPACE = stop motors
  U  = forward_until (drive toward wall, LiDAR-based)
  F  = wall_follow_left for 3s
  G  = wall_follow_right for 3s
  P  = print recorded route so far
  C  = clear all recorded steps
  X  = undo last step
  Q  = quit and print final route

The tool publishes to /cmd_vel so safety_gate handles motors and obstacle avoidance.
It records each movement with its duration.

Requires safety_gate and nav_hardware_launch.py to be running.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
import sys
import time
import math
import json

# Same speeds as route_executor
FORWARD_VEL = 0.10
TURN_VEL = 0.6
TIME_90_DEG = 2.2

# LiDAR arcs (same as route_executor)
FRONT_ARC = math.radians(60)
SIDE_ARC = math.radians(30)


class RouteTeacher(Node):
    def __init__(self):
        super().__init__('teach_route')

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self._on_scan, 10)

        self.front_dist = float('inf')
        self.left_dist = float('inf')
        self.right_dist = float('inf')

        self.recorded = []
        self.current_action = None
        self.action_start = None

        self.get_logger().info('=' * 50)
        self.get_logger().info('ROUTE TEACHER')
        self.get_logger().info('=' * 50)
        self.get_logger().info('W=forward  S=backward  A=left  D=right')
        self.get_logger().info('SPACE=stop  U=until_wall  F=wall_L  G=wall_R')
        self.get_logger().info('P=print  C=clear  X=undo  Q=quit')
        self.get_logger().info('=' * 50)

    def _on_scan(self, msg):
        front = float('inf')
        left = float('inf')
        right = float('inf')
        angle = msg.angle_min
        for r in msg.ranges:
            if msg.range_min < r < msg.range_max:
                if (math.pi - abs(angle)) <= FRONT_ARC:
                    front = min(front, r)
                if abs(angle - (-math.pi / 2)) <= SIDE_ARC:
                    left = min(left, r)
                if abs(angle - (math.pi / 2)) <= SIDE_ARC:
                    right = min(right, r)
            angle += msg.angle_increment
        self.front_dist = front
        self.left_dist = left
        self.right_dist = right

    def _pub(self, lx, az):
        msg = Twist()
        msg.linear.x = float(lx)
        msg.angular.z = float(az)
        self.cmd_pub.publish(msg)

    def _stop_motors(self):
        self._pub(0, 0)

    def _end_current_action(self):
        """Stop current action and record it."""
        if self.current_action and self.action_start:
            duration = round(time.time() - self.action_start, 1)
            if duration >= 0.3:
                step = None
                if self.current_action == 'forward':
                    step = {'action': 'forward_for', 'duration': duration}
                elif self.current_action == 'backward':
                    step = {'action': 'backward_for', 'duration': duration}
                elif self.current_action == 'left':
                    # Estimate degrees from time
                    degs = int(round(duration / TIME_90_DEG * 90))
                    step = {'action': 'turn_left', 'degrees': min(degs, 360)}
                elif self.current_action == 'right':
                    degs = int(round(duration / TIME_90_DEG * 90))
                    step = {'action': 'turn_right', 'degrees': min(degs, 360)}

                if step:
                    self.recorded.append(step)
                    self.get_logger().info(f'  Recorded: {step}')

        self.current_action = None
        self.action_start = None
        self._stop_motors()

    def _start_action(self, action_name):
        """Start a new movement action."""
        # If same action already running, treat as toggle-off
        if self.current_action == action_name:
            self._end_current_action()
            return

        # End any previous action
        self._end_current_action()

        self.current_action = action_name
        self.action_start = time.time()

        if action_name == 'forward':
            self._pub(FORWARD_VEL, 0)
            self.get_logger().info('  -> Forward...')
        elif action_name == 'backward':
            self._pub(-FORWARD_VEL, 0)
            self.get_logger().info('  -> Backward...')
        elif action_name == 'left':
            self._pub(0, TURN_VEL)
            self.get_logger().info('  -> Turning left...')
        elif action_name == 'right':
            self._pub(0, -TURN_VEL)
            self.get_logger().info('  -> Turning right...')

    def _do_forward_until(self, target=0.5):
        """Drive forward until wall, record as forward_until step."""
        self._end_current_action()
        self.get_logger().info(f'  -> Forward until wall < {target}m ...')

        if self.front_dist == float('inf'):
            self.get_logger().warn('  No LiDAR! Skipping')
            return

        while self.front_dist > target:
            if self.front_dist < target + 0.15:
                self._pub(0.06, 0)
            else:
                self._pub(FORWARD_VEL, 0)
            rclpy.spin_once(self, timeout_sec=0.05)

        self._stop_motors()
        step = {'action': 'forward_until', 'distance': target}
        self.recorded.append(step)
        self.get_logger().info(f'  Recorded: {step}')

    def _do_wall_follow(self, side, duration=3.0, target=0.4):
        """Wall follow for N seconds, record step."""
        self._end_current_action()
        self.get_logger().info(f'  -> Wall follow {side} at {target}m for {duration}s ...')

        start = time.time()
        while time.time() - start < duration:
            dist = self.left_dist if side == 'left' else self.right_dist
            correction = 0.0
            if dist < 8.0:
                error = target - dist
                correction = 1.5 * error if side == 'left' else -1.5 * error
                correction = max(-0.3, min(0.3, correction))
            self._pub(FORWARD_VEL, correction)
            rclpy.spin_once(self, timeout_sec=0.05)

        self._stop_motors()
        action_name = f'wall_follow_{side}'
        step = {'action': action_name, 'distance': target, 'duration': duration}
        self.recorded.append(step)
        self.get_logger().info(f'  Recorded: {step}')

    def print_route(self):
        self.get_logger().info('')
        self.get_logger().info('=' * 55)
        self.get_logger().info('RECORDED ROUTE - Copy this into route_executor.py')
        self.get_logger().info('=' * 55)
        self.get_logger().info('')
        self.get_logger().info("    'your_route_name': {")
        self.get_logger().info("        'display_name': 'Your Route Name',")
        self.get_logger().info("        'aliases': ['alias1', 'alias2'],")
        self.get_logger().info("        'wait_time': 5,")
        self.get_logger().info("        'steps': [")
        self.get_logger().info("            {'action': 'announce', 'text': 'Heading to destination'},")
        for step in self.recorded:
            self.get_logger().info(f'            {step},')
        self.get_logger().info("            {'action': 'announce', 'text': 'Arrived'},")
        self.get_logger().info("            {'action': 'stop'},")
        self.get_logger().info("        ],")

        # Auto-generate return steps (reverse)
        self.get_logger().info("        'return_steps': [")
        self.get_logger().info("            {'action': 'announce', 'text': 'Returning home'},")
        for step in reversed(self.recorded):
            rev = self._reverse_step(step)
            if rev:
                self.get_logger().info(f'            {rev},')
        self.get_logger().info("            {'action': 'announce', 'text': 'Back home'},")
        self.get_logger().info("            {'action': 'stop'},")
        self.get_logger().info("        ],")

        self.get_logger().info("    },")
        self.get_logger().info('')
        self.get_logger().info('=' * 55)

    def _reverse_step(self, step):
        """Generate the reverse of a step for return route."""
        action = step['action']
        if action == 'forward_for':
            return {'action': 'backward_for', 'duration': step['duration']}
        elif action == 'backward_for':
            return {'action': 'forward_for', 'duration': step['duration']}
        elif action == 'turn_left':
            return {'action': 'turn_right', 'degrees': step['degrees']}
        elif action == 'turn_right':
            return {'action': 'turn_left', 'degrees': step['degrees']}
        elif action == 'forward_until':
            # Can't reverse forward_until, use backward_for 1s as placeholder
            return {'action': 'backward_for', 'duration': 1.5}
        elif action.startswith('wall_follow'):
            # Reverse wall follow: same wall, same params
            return step.copy()
        return None

    def run_interactive(self):
        """Main interactive loop using stdin."""
        import select
        import termios
        import tty

        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())

            self.get_logger().info('Ready! Use WASD to drive, Q to quit.')
            self.get_logger().info(f'  Front: {self.front_dist:.2f}m  Left: {self.left_dist:.2f}m  Right: {self.right_dist:.2f}m')

            while rclpy.ok():
                rclpy.spin_once(self, timeout_sec=0.05)

                if select.select([sys.stdin], [], [], 0.05)[0]:
                    key = sys.stdin.read(1).lower()

                    if key == 'w':
                        self._start_action('forward')
                    elif key == 's':
                        self._start_action('backward')
                    elif key == 'a':
                        self._start_action('left')
                    elif key == 'd':
                        self._start_action('right')
                    elif key == ' ':
                        self._end_current_action()
                        self.get_logger().info('  Stopped')
                    elif key == 'u':
                        self._do_forward_until(0.5)
                    elif key == 'f':
                        self._do_wall_follow('left', 3.0, 0.4)
                    elif key == 'g':
                        self._do_wall_follow('right', 3.0, 0.4)
                    elif key == 'p':
                        self._end_current_action()
                        self.print_route()
                    elif key == 'c':
                        self._end_current_action()
                        self.recorded = []
                        self.get_logger().info('  Route cleared')
                    elif key == 'x':
                        self._end_current_action()
                        if self.recorded:
                            removed = self.recorded.pop()
                            self.get_logger().info(f'  Undid: {removed}')
                        else:
                            self.get_logger().info('  Nothing to undo')
                    elif key == 'q':
                        self._end_current_action()
                        break

                # Show live distances periodically (every ~1s)
                # (simplified: just show on action changes)

        except Exception as e:
            self.get_logger().error(f'Error: {e}')
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            self._stop_motors()

        # Final output
        if self.recorded:
            self.print_route()
        else:
            self.get_logger().info('No steps recorded.')


def main():
    rclpy.init()
    node = RouteTeacher()
    try:
        node.run_interactive()
    except KeyboardInterrupt:
        pass
    finally:
        node._stop_motors()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
