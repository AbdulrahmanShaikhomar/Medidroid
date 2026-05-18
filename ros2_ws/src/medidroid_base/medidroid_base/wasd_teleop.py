import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import sys
import tty
import termios

class WASDTeleop(Node):
    def __init__(self):
        super().__init__('wasd_teleop')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)
        self.settings = termios.tcgetattr(sys.stdin)
        self.get_logger().info("WASD Teleop Control Started.")
        self.get_logger().info("Use W/A/S/D to move. Press Space to stop. Press Q to quit.")
        
        # Very slow speed as requested
        self.linear_speed = 0.35  
        self.angular_speed = 0.6  
        
    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        key = sys.stdin.read(1)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
        return key

    def run(self):
        try:
            while rclpy.ok():
                key = self.get_key().lower()
                msg = Twist()
                
                if key == 'w':
                    msg.linear.x = self.linear_speed
                elif key == 's':
                    msg.linear.x = -self.linear_speed
                elif key == 'a':
                    msg.angular.z = self.angular_speed
                elif key == 'd':
                    msg.angular.z = -self.angular_speed
                elif key == ' ':
                    pass # Stop parsing, leave speeds 0
                elif key == 'q':
                    break
                else:
                    continue
                
                self.publisher_.publish(msg)
                
        except Exception as e:
            self.get_logger().error(f"Error: {e}")
        finally:
            msg = Twist()
            self.publisher_.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = WASDTeleop()
    node.run()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
