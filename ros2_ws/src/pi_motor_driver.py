#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from gpiozero import OutputDevice

# L298N #1 - LEFT SIDE
L_IN1 = OutputDevice(17)
L_IN2 = OutputDevice(27)
L_IN3 = OutputDevice(22)
L_IN4 = OutputDevice(23)

# L298N #2 - RIGHT SIDE
R_IN1 = OutputDevice(24)
R_IN2 = OutputDevice(25)
R_IN3 = OutputDevice(12)
R_IN4 = OutputDevice(16)

def left_forward():  L_IN1.on();  L_IN2.off(); L_IN3.on();  L_IN4.off()
def left_backward(): L_IN1.off(); L_IN2.on();  L_IN3.off(); L_IN4.on()
def left_stop():     L_IN1.off(); L_IN2.off(); L_IN3.off(); L_IN4.off()

def right_forward():  R_IN1.on();  R_IN2.off(); R_IN3.on();  R_IN4.off()
def right_backward(): R_IN1.off(); R_IN2.on();  R_IN3.off(); R_IN4.on()
def right_stop():     R_IN1.off(); R_IN2.off(); R_IN3.off(); R_IN4.off()

def all_stop():  left_stop();  right_stop()

class MotorDriver(Node):
    def __init__(self):
        super().__init__('pi_motor_driver')
        self.sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_callback, 10)
        all_stop()
        self.get_logger().info('Pi Motor Driver Ready (2x L298N)')

    def cmd_callback(self, msg):
        lin = msg.linear.x
        ang = msg.angular.z

        if lin > 0.05:          # Forward
            left_forward(); right_forward()
        elif lin < -0.05:       # Backward
            left_backward(); right_backward()
        elif ang > 0.05:        # Turn Left (spin in place)
            left_backward(); right_forward()
        elif ang < -0.05:       # Turn Right (spin in place)
            left_forward(); right_backward()
        else:                   # Stop
            all_stop()

def main(args=None):
    rclpy.init(args=args)
    node = MotorDriver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        all_stop()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
