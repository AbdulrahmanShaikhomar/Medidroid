import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from action_msgs.msg import GoalStatus
import math
import sys
import time


# ── Coordinates: (x, y, yaw) from real map measurements ──

ROOMS = {
    'room_101': (-5.3, 5.4, 0.00311),
    'room_102': (-5.36, 19.6, 0.00246),
    'room_205': (-16.4, 46.8, -0.00102),
    'room_206': (-27.1, 25.9, 0.00368),
    'room_301': (-27.5, 11.6, -0.00108),
    'room_302': (-27.8, -18.7, 0.00306),
    'room_401': (-28.4, -35.4, 0.00399),
    'room_402': (-28.4, -32.4, 0.00354),
}

HALLWAYS = {
    'hall_1': (-5.21, 2.91, 0.0235),
    'hall_2': (-27.8, 1.64, 1.45),
    'hall_3': (-27.6, -3.28, 1.43),
    'hall_4': (-53.6, 3.0, 1.49),
    'hall_5': (-52.6, -3.2, 1.39),
    'hall_6': (-74.3, -2.74, 1.49),
    'hall_7': (-74.6, 3.8, 1.44),
    'hall_8': (-98.5, -2.94, 0.0116),
    'hall_9': (-97.8, 1.81, 0.0225),
}

HOME = (-1.54, 3.15, -0.00871)

# ── Departments → coordinates ──

DEPARTMENTS = {
    'cardiology':  'hall_1',
    'neurology':   'hall_2',
    'pediatrics':  'hall_3',
    'orthopedics': 'hall_4',
    'emergency':   'hall_5',
}

DEPARTMENT_ALIASES = {
    'heart': 'cardiology', 'cardio': 'cardiology', 'cardiac': 'cardiology',
    'brain': 'neurology', 'neuro': 'neurology', 'nerves': 'neurology',
    'children': 'pediatrics', 'kids': 'pediatrics', 'child clinic': 'pediatrics',
    'bones': 'orthopedics', 'ortho': 'orthopedics', 'joints': 'orthopedics',
    'er': 'emergency', 'emergency room': 'emergency', 'casualty': 'emergency',
    'urgent care': 'emergency', 'trauma center': 'emergency',
}

# ── Doctors → room mapping ──

DOCTORS = {
    'dr_tariq':  {'full': 'Dr. Tariq Ahmed Al-Farsi',   'dept': 'cardiology',  'room': 'room_101', 'specialties': ['cardiologist', 'heart doctor']},
    'dr_sara':   {'full': 'Dr. Sara Mohammed Al-Ghamdi', 'dept': 'cardiology',  'room': 'room_102', 'specialties': ['cardiac surgeon', 'heart surgeon']},
    'dr_omar':   {'full': 'Dr. Omar Khalid Al-Farsi',    'dept': 'neurology',   'room': 'room_205', 'specialties': ['neurologist', 'brain surgeon']},
    'dr_reem':   {'full': 'Dr. Reem Faisal Al-Mutairi',  'dept': 'neurology',   'room': 'room_206', 'specialties': ['neurologist', 'nerve doctor', 'brain doctor']},
    'dr_nada':   {'full': 'Dr. Nada Abdullah Al-Ghamdi', 'dept': 'pediatrics',  'room': 'room_301', 'specialties': ['pediatrician', 'kids doctor', 'child care']},
    'dr_maha':   {'full': 'Dr. Maha Yousef Al-Shammari', 'dept': 'pediatrics',  'room': 'room_302', 'specialties': ['pediatrician', 'children specialist', 'baby doctor']},
    'dr_faisal': {'full': 'Dr. Faisal Nasser Al-Harbi',  'dept': 'orthopedics', 'room': 'room_401', 'specialties': ['orthopedic surgeon', 'bone doctor', 'joint doctor']},
    'dr_huda':   {'full': 'Dr. Huda Saeed Al-Qahtani',   'dept': 'orthopedics', 'room': 'room_402', 'specialties': ['orthopedist', 'spine doctor', 'mobility specialist']},
}

DOCTOR_ALIASES = {
    'tariq': 'dr_tariq', 'tarek': 'dr_tariq', 'ahmed': 'dr_tariq', 'al-farsi': 'dr_tariq',
    'sara': 'dr_sara', 'sarah': 'dr_sara', 'al-ghamdi': 'dr_sara',
    'omar': 'dr_omar', 'khalid': 'dr_omar',
    'reem': 'dr_reem', 'al-mutairi': 'dr_reem',
    'nada': 'dr_nada',
    'maha': 'dr_maha', 'al-shammari': 'dr_maha',
    'faisal': 'dr_faisal', 'al-harbi': 'dr_faisal',
    'huda': 'dr_huda', 'al-qahtani': 'dr_huda',
}

# ── Speed profiles ──

SPEED_PROFILES = {
    'fast':   {'pwm': 255, 'linear': 0.500},
    'medium': {'pwm': 170, 'linear': 0.333},
    'easy':   {'pwm': 85,  'linear': 0.167},
}

WAIT_AT_DESTINATION = 5.0


def yaw_to_quaternion(yaw):
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def resolve_target(name):
    """Resolve any name (room, hallway, department, doctor, alias) to (x, y, yaw, label)."""
    name = name.lower().strip()

    # Direct room match
    if name in ROOMS:
        x, y, yaw = ROOMS[name]
        return x, y, yaw, name

    # Direct hallway match
    if name in HALLWAYS:
        x, y, yaw = HALLWAYS[name]
        return x, y, yaw, name

    # Department match
    dept = None
    if name in DEPARTMENTS:
        dept = name
    elif name in DEPARTMENT_ALIASES:
        dept = DEPARTMENT_ALIASES[name]
    if dept:
        room_key = DEPARTMENTS[dept]
        if room_key in ROOMS:
            x, y, yaw = ROOMS[room_key]
        else:
            x, y, yaw = HALLWAYS[room_key]
        return x, y, yaw, f'{dept} ({room_key})'

    # Doctor match
    doc = None
    if name in DOCTORS:
        doc = name
    elif name in DOCTOR_ALIASES:
        doc = DOCTOR_ALIASES[name]
    if doc:
        room_key = DOCTORS[doc]['room']
        x, y, yaw = ROOMS[room_key]
        return x, y, yaw, f'{DOCTORS[doc]["full"]} ({room_key})'

    return None


class GoToNode(Node):
    def __init__(self):
        super().__init__('go_to')
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.get_logger().info('Waiting for Nav2 action server...')
        self.nav_client.wait_for_server()
        self.get_logger().info('Nav2 ready.')

    def send_goal(self, x, y, yaw, label=''):
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(x)
        goal.pose.pose.position.y = float(y)
        _, _, qz, qw = yaw_to_quaternion(yaw)
        goal.pose.pose.orientation.z = qz
        goal.pose.pose.orientation.w = qw

        self.get_logger().info(f'>> Navigating to {label} ({x:.1f}, {y:.1f})')
        future = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error(f'Goal rejected for {label}')
            return False

        self.get_logger().info(f'Moving to {label}...')
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result()
        if result.status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f'Arrived at {label}!')
            return True
        else:
            self.get_logger().warn(f'Failed to reach {label} (status={result.status})')
            return False

    def go_home(self):
        x, y, yaw = HOME
        return self.send_goal(x, y, yaw, 'HOME')


def print_all(logger):
    logger.info('=== DEPARTMENTS ===')
    for dept, room in sorted(DEPARTMENTS.items()):
        logger.info(f'  {dept} -> {room}')
    logger.info('=== DOCTORS ===')
    for key, doc in sorted(DOCTORS.items()):
        logger.info(f'  {key}: {doc["full"]} [{doc["dept"]}] -> {doc["room"]}')
    logger.info('=== ROOMS ===')
    for name, (x, y, yaw) in sorted(ROOMS.items()):
        logger.info(f'  {name}: ({x}, {y})')
    logger.info('=== HALLWAYS ===')
    for name, (x, y, yaw) in sorted(HALLWAYS.items()):
        logger.info(f'  {name}: ({x}, {y})')
    logger.info(f'=== HOME: ({HOME[0]}, {HOME[1]}) ===')


def main():
    rclpy.init()
    node = GoToNode()

    target = 'room_101'
    wait_time = WAIT_AT_DESTINATION

    node.declare_parameter('target', target)
    node.declare_parameter('wait', wait_time)
    target = node.get_parameter('target').get_parameter_value().string_value
    wait_time = node.get_parameter('wait').get_parameter_value().double_value

    if target == 'list':
        print_all(node.get_logger())
        node.destroy_node()
        rclpy.shutdown()
        return

    if target == 'home':
        node.go_home()
        node.destroy_node()
        rclpy.shutdown()
        return

    resolved = resolve_target(target)
    if resolved is None:
        node.get_logger().error(f'Unknown target: "{target}"')
        node.get_logger().info('Use target:=list to see all options')
        node.destroy_node()
        rclpy.shutdown()
        return

    x, y, yaw, label = resolved
    arrived = node.send_goal(x, y, yaw, label)

    if arrived:
        node.get_logger().info(f'Waiting {wait_time}s at {label}...')
        time.sleep(wait_time)

    node.get_logger().info('Returning to HOME...')
    node.go_home()

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
