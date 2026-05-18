import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
import serial
import time
import math
import tf2_ros

class Esp32MotorDriver(Node):
    def __init__(self):
        super().__init__('esp32_motor_driver')
        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('wheel_radius', 0.0325)
        self.declare_parameter('wheel_base', 0.15)
        self.declare_parameter('ticks_per_rev', 330.0)
        
        self.port_name = self.get_parameter('serial_port').value
        self.baud_rate = self.get_parameter('baud_rate').value
        self.r = self.get_parameter('wheel_radius').value
        self.b = self.get_parameter('wheel_base').value
        self.ticks_per_rev = self.get_parameter('ticks_per_rev').value
        
        self.subscription = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)
        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        try:
            self.serial_conn = serial.Serial(self.port_name, self.baud_rate, timeout=0.1)
            time.sleep(2)
            self.get_logger().info(f"Connected to ESP32 on {self.port_name}")
        except Exception as e:
            self.get_logger().error(f"Failed to connect: {e}")
            self.serial_conn = None

        self.x = 0.0
        self.y = 0.0
        self.th = 0.0
        self.last_ticks_L = 0
        self.last_ticks_R = 0
        self.last_time = self.get_clock().now()
        self.reader_timer = self.create_timer(0.05, self.read_serial_data)

    def cmd_vel_callback(self, msg):
        if self.serial_conn is None: return
        v = msg.linear.x
        w = msg.angular.z
        # Speed mapping: v=0.5m/s -> 255 PWM
        speed_L = int((v - w * self.b / 2.0) * 510)
        speed_R = int((v + w * self.b / 2.0) * 510)
        speed_L = max(-255, min(255, speed_L))
        speed_R = max(-255, min(255, speed_R))
        try:
            self.serial_conn.write(f"{speed_L},{speed_R}\n".encode('utf-8'))
        except Exception as e:
            self.get_logger().error(f"Serial Write Error: {e}")

    def read_serial_data(self):
        if self.serial_conn is None: return
        try:
            while self.serial_conn.in_waiting > 0:
                line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) == 2:
                        try:
                            ticks_L = int(parts[0])
                            ticks_R = int(parts[1])
                            self.update_odometry(ticks_L, ticks_R)
                        except: pass
        except Exception as e:
             self.get_logger().error(f"Serial Read Error: {e}")

    def update_odometry(self, ticks_L, ticks_R):
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        if dt <= 0: return

        d_L = (ticks_L - self.last_ticks_L) * (2.0 * math.pi * self.r) / self.ticks_per_rev
        d_R = (ticks_R - self.last_ticks_R) * (2.0 * math.pi * self.r) / self.ticks_per_rev
        d = (d_L + d_R) / 2.0
        d_th = (d_R - d_L) / self.b
        self.x += d * math.cos(self.th)
        self.y += d * math.sin(self.th)
        self.th += d_th
        
        t = TransformStamped()
        t.header.stamp = now.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.rotation.z = math.sin(self.th / 2.0)
        t.transform.rotation.w = math.cos(self.th / 2.0)
        self.tf_broadcaster.sendTransform(t)
        
        odom = Odometry()
        odom.header.stamp = now.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = math.sin(self.th / 2.0)
        odom.pose.pose.orientation.w = math.cos(self.th / 2.0)
        self.odom_pub.publish(odom)
        
        self.last_ticks_L = ticks_L
        self.last_ticks_R = ticks_R
        self.last_time = now

def main(args=None):
    rclpy.init(args=args)
    node = Esp32MotorDriver()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
