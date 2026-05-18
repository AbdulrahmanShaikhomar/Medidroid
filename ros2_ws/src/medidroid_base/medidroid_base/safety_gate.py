import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import serial
import threading
import time

DRIVE_PWM = 200
RIGHT_SCALE = 0.80
TURN_INNER = 0.0


class CarStyleBridge(Node):
    def __init__(self):
        super().__init__('safety_gate')
        self.ser = None
        try:
            self.ser = serial.Serial('/dev/ttyESP32', 115200, timeout=0.05)
            self.get_logger().info('ESP32 connected')
        except Exception as e:
            self.get_logger().error(f'ESP32 not found: {e}')

        self.cmd_sub = self.create_subscription(Twist, '/cmd_vel', self.cmd_callback, 10)

        if self.ser:
            self.drain_thread = threading.Thread(target=self._drain_serial, daemon=True)
            self.drain_thread.start()

        self.get_logger().info('safety_gate ready - decisive mode')

    def _drain_serial(self):
        while rclpy.ok():
            try:
                if self.ser and self.ser.in_waiting:
                    self.ser.read(self.ser.in_waiting)
                else:
                    time.sleep(0.05)
            except Exception:
                time.sleep(0.1)

    def cmd_callback(self, msg):
        if not self.ser:
            return
        try:
            v = msg.linear.x
            w = msg.angular.z

            if abs(v) < 0.01 and abs(w) < 0.01:
                self.ser.write(b'M,0,0\n')
                return

            # Reverse (Nav2 says backward = our physical forward now)
            if v < -0.05:
                pwm_l = DRIVE_PWM
                pwm_r = int(DRIVE_PWM * RIGHT_SCALE)
                cmd = f'M,{pwm_l},{pwm_r}\n'
                self.ser.write(cmd.encode())
                self.get_logger().info(f'REVERSE -> {cmd.strip()}')
                return

            # Forward in Nav2 = physical backward
            if abs(v) < 0.05:
                turn_ratio = 1.0
            else:
                turn_ratio = min(abs(w) / abs(v), 1.0)

            # Turning = slow down the inner wheel
            inner_factor = 1.0 - (turn_ratio * (1.0 - TURN_INNER))

            if w > 0.05:
                # Turn left: slow left wheel
                pwm_l = int(-DRIVE_PWM * inner_factor)
                pwm_r = int(-DRIVE_PWM * RIGHT_SCALE)
            elif w < -0.05:
                # Turn right: slow right wheel
                pwm_l = -DRIVE_PWM
                pwm_r = int(-DRIVE_PWM * RIGHT_SCALE * inner_factor)
            else:
                # Straight
                pwm_l = -DRIVE_PWM
                pwm_r = int(-DRIVE_PWM * RIGHT_SCALE)

            cmd = f'M,{pwm_l},{pwm_r}\n'
            self.ser.write(cmd.encode())
            self.get_logger().info(f'v={v:.2f} w={w:.2f} r={turn_ratio:.2f} -> {cmd.strip()}')
        except Exception as e:
            self.get_logger().error(f'Error: {e}')


def main():
    rclpy.init()
    node = CarStyleBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
