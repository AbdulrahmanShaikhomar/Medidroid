"""
MediDroid Voice Command Node
─────────────────────────────
Listens for spoken navigation commands via microphone (Vosk offline STT),
resolves the target using the hospital database, and sends Nav2 goals.

Commands understood:
  "go to cardiology"          → navigates to department
  "take me to doctor tariq"   → navigates to doctor's room
  "navigate to room 101"      → navigates to room
  "go to emergency"           → navigates to ER hallway
  "go home"                   → navigates to HOME
  "stop" / "cancel"           → cancels current navigation
  "list destinations"         → speaks all available destinations
  "where am i"                → speaks current position

Requires: vosk, pyaudio, flite (TTS)
  pip install vosk pyaudio sounddevice
  sudo apt install flite
  Download model: vosk-model-small-en-us-0.15
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
import math
import json
import os
import subprocess
import threading
import time

# ── Import shared hospital database from go_to ──
from medidroid_base.go_to import (
    ROOMS, HALLWAYS, HOME, DEPARTMENTS, DEPARTMENT_ALIASES,
    DOCTORS, DOCTOR_ALIASES, SPEED_PROFILES, WAIT_AT_DESTINATION,
    yaw_to_quaternion, resolve_target,
)

# ── Vosk model path (download once on Pi) ──
VOSK_MODEL_PATHS = [
    os.path.expanduser('~/vosk-model-small-en-us-0.15'),
    os.path.expanduser('~/vosk-model'),
    '/opt/vosk/model',
    os.path.expanduser('~/ros2_ws/vosk-model'),
]

SAMPLE_RATE = 16000
CHUNK_SIZE = 4000  # ~250ms of audio at 16kHz


def speak(text, logger=None):
    """Text-to-speech using flite (non-blocking)."""
    if logger:
        logger.info(f'[TTS] {text}')
    try:
        subprocess.Popen(
            ['flite', '-t', text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        # flite not installed, try espeak-ng
        try:
            subprocess.Popen(
                ['espeak-ng', '-s', '140', text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            if logger:
                logger.warn('No TTS engine found (flite or espeak-ng)')


def parse_navigation_command(text):
    """
    Extract a navigation target from spoken text.
    Returns (target_name, command_type) or (None, None).

    command_type: 'navigate', 'home', 'stop', 'list', 'status'
    """
    text = text.lower().strip()

    if not text:
        return None, None

    # ── Stop / Cancel ──
    stop_phrases = ['stop', 'cancel', 'halt', 'abort', 'freeze']
    for phrase in stop_phrases:
        if phrase in text:
            return None, 'stop'

    # ── Go home ──
    home_phrases = ['go home', 'return home', 'come back', 'go back home',
                    'return to base', 'go to home', 'back home', 'home base']
    for phrase in home_phrases:
        if phrase in text:
            return 'home', 'home'

    # ── List destinations ──
    list_phrases = ['list', 'what destinations', 'where can you go',
                    'show destinations', 'available destinations', 'what places']
    for phrase in list_phrases:
        if phrase in text:
            return None, 'list'

    # ── Status ──
    status_phrases = ['where am i', 'current location', 'where are you',
                      'what is your position', 'status']
    for phrase in status_phrases:
        if phrase in text:
            return None, 'status'

    # ── Navigation commands ──
    # Strip common prefixes
    nav_prefixes = [
        'go to ', 'navigate to ', 'take me to ', 'drive to ',
        'head to ', 'move to ', 'bring me to ', 'visit ',
        'go to the ', 'take me to the ', 'navigate to the ',
        'head to the ', 'drive to the ', 'move to the ',
    ]

    target_text = None
    for prefix in sorted(nav_prefixes, key=len, reverse=True):
        if text.startswith(prefix):
            target_text = text[len(prefix):].strip()
            break

    if target_text is None:
        # Also try: "doctor tariq" or "room 101" without prefix
        if text.startswith('doctor ') or text.startswith('dr '):
            target_text = text
        elif text.startswith('room '):
            target_text = text
        else:
            return None, None

    if not target_text:
        return None, None

    # ── Clean up target text ──
    # "doctor tariq" → "dr_tariq" style, "room 101" → "room_101"
    target_text = target_text.strip(' .')

    # Try direct resolve first
    resolved = resolve_target(target_text)
    if resolved:
        return target_text, 'navigate'

    # Try "room_XXX" format
    if target_text.startswith('room '):
        room_num = target_text.replace('room ', 'room_')
        resolved = resolve_target(room_num)
        if resolved:
            return room_num, 'navigate'

    # Try "hall_X" format
    if target_text.startswith('hall ') or target_text.startswith('hallway '):
        hall_num = target_text.replace('hallway ', 'hall_').replace('hall ', 'hall_')
        resolved = resolve_target(hall_num)
        if resolved:
            return hall_num, 'navigate'

    # Try "dr_name" format for "doctor name" or "dr name"
    name_part = target_text
    for prefix in ['doctor ', 'dr ', 'dr. ']:
        if name_part.startswith(prefix):
            name_part = name_part[len(prefix):]
            break

    # Try doctor first name
    resolved = resolve_target(name_part)
    if resolved:
        return name_part, 'navigate'

    # Try with dr_ prefix
    dr_key = f'dr_{name_part.split()[0]}'
    resolved = resolve_target(dr_key)
    if resolved:
        return dr_key, 'navigate'

    # Try specialty match: "bone doctor" → orthopedics doctor
    for doc_key, doc_info in DOCTORS.items():
        for spec in doc_info['specialties']:
            if spec in target_text or target_text in spec:
                return doc_key, 'navigate'

    # Try fuzzy department match
    for dept in DEPARTMENTS:
        if dept in target_text or target_text in dept:
            return dept, 'navigate'

    # Try alias scan
    for alias in DEPARTMENT_ALIASES:
        if alias in target_text or target_text in alias:
            return alias, 'navigate'

    for alias in DOCTOR_ALIASES:
        if alias in target_text or target_text in alias:
            return alias, 'navigate'

    return target_text, 'unknown'


class VoiceCommandNode(Node):
    def __init__(self):
        super().__init__('voice_command')

        # ── Parameters ──
        self.declare_parameter('model_path', '')
        self.declare_parameter('use_mic', True)
        self.declare_parameter('wake_word', 'medidroid')
        self.declare_parameter('require_wake_word', False)
        self.declare_parameter('wait_at_destination', WAIT_AT_DESTINATION)

        self.model_path = self.get_parameter('model_path').get_parameter_value().string_value
        self.use_mic = self.get_parameter('use_mic').get_parameter_value().bool_value
        self.wake_word = self.get_parameter('wake_word').get_parameter_value().string_value
        self.require_wake = self.get_parameter('require_wake_word').get_parameter_value().bool_value
        self.wait_time = self.get_parameter('wait_at_destination').get_parameter_value().double_value

        # ── State ──
        self.is_navigating = False
        self.current_goal_handle = None
        self.current_label = ''

        # ── Nav2 action client ──
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # ── Text command subscriber (alternative to mic — other nodes can publish) ──
        self.text_sub = self.create_subscription(
            String, '/voice_text', self.text_command_callback, 10
        )

        # ── Status publisher ──
        self.status_pub = self.create_publisher(String, '/medidroid_status', 10)

        self.get_logger().info('Voice command node starting...')

        # ── Wait for Nav2 ──
        self.get_logger().info('Waiting for Nav2 action server...')
        if not self.nav_client.wait_for_server(timeout_sec=15.0):
            self.get_logger().warn('Nav2 not available yet — will retry when command received')
        else:
            self.get_logger().info('Nav2 ready.')

        # ── Start mic listening thread ──
        if self.use_mic:
            self.mic_thread = threading.Thread(target=self._mic_loop, daemon=True)
            self.mic_thread.start()
        else:
            self.get_logger().info('Mic disabled — listening on /voice_text topic only')

        speak('MediDroid voice command ready', self.get_logger())
        self.publish_status('ready')

    def publish_status(self, status):
        msg = String()
        msg.data = status
        self.status_pub.publish(msg)

    # ── Microphone listening loop ──

    def _mic_loop(self):
        """Continuous mic → Vosk → command processing."""
        try:
            import vosk
            import pyaudio
        except ImportError as e:
            self.get_logger().error(
                f'Missing dependency: {e}. Install with: pip install vosk pyaudio'
            )
            return

        # Find model
        model_path = self.model_path
        if not model_path:
            for path in VOSK_MODEL_PATHS:
                if os.path.isdir(path):
                    model_path = path
                    break

        if not model_path or not os.path.isdir(model_path):
            self.get_logger().error(
                'Vosk model not found! Download it:\n'
                '  cd ~ && wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip\n'
                '  unzip vosk-model-small-en-us-0.15.zip'
            )
            self.get_logger().info('Falling back to /voice_text topic only')
            return

        self.get_logger().info(f'Loading Vosk model from {model_path}...')
        model = vosk.Model(model_path)
        recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(True)

        # Open microphone
        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
            )
        except Exception as e:
            self.get_logger().error(f'Cannot open microphone: {e}')
            self.get_logger().info('Falling back to /voice_text topic only')
            pa.terminate()
            return

        self.get_logger().info('Microphone listening...')
        speak('Listening for commands', self.get_logger())

        wake_active = not self.require_wake
        wake_timeout = 0

        while rclpy.ok():
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                time.sleep(0.1)
                continue

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get('text', '').strip()
                if not text:
                    continue

                self.get_logger().info(f'[STT] Heard: "{text}"')

                # Wake word handling
                if self.require_wake and not wake_active:
                    if self.wake_word in text.lower():
                        wake_active = True
                        wake_timeout = time.time() + 10.0  # 10s window
                        speak('Yes? What would you like?', self.get_logger())
                        self.get_logger().info('Wake word detected — listening for command...')
                    continue

                if self.require_wake and wake_active and time.time() > wake_timeout:
                    wake_active = False
                    continue

                # Process the command
                self._process_text(text)

                if self.require_wake:
                    wake_active = False
            else:
                # Partial result — could show for feedback
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get('partial', '')
                if partial_text and len(partial_text) > 3:
                    pass  # Could log partial for debugging

        stream.stop_stream()
        stream.close()
        pa.terminate()

    # ── Text command callback (from /voice_text topic) ──

    def text_command_callback(self, msg):
        """Handle text commands published to /voice_text."""
        text = msg.data.strip()
        if text:
            self.get_logger().info(f'[TEXT] Received: "{text}"')
            self._process_text(text)

    # ── Command processor ──

    def _process_text(self, text):
        """Parse text and execute navigation command."""
        target_name, cmd_type = parse_navigation_command(text)

        if cmd_type is None:
            # Not a recognized command pattern — ignore
            return

        if cmd_type == 'stop':
            self._handle_stop()

        elif cmd_type == 'home':
            self._handle_navigate_home()

        elif cmd_type == 'list':
            self._handle_list()

        elif cmd_type == 'status':
            self._handle_status()

        elif cmd_type == 'navigate':
            self._handle_navigate(target_name)

        elif cmd_type == 'unknown':
            speak(f'Sorry, I do not know where {target_name} is.', self.get_logger())
            self.get_logger().warn(f'Unknown target: "{target_name}"')

    # ── Navigation handlers ──

    def _handle_navigate(self, target_name):
        resolved = resolve_target(target_name)
        if resolved is None:
            speak(f'I cannot find {target_name}. Please try again.', self.get_logger())
            return

        x, y, yaw, label = resolved

        if self.is_navigating:
            speak(f'Cancelling current trip. Now heading to {label}.', self.get_logger())
            self._cancel_current_goal()
            time.sleep(0.5)

        speak(f'Navigating to {label}', self.get_logger())
        self.publish_status(f'navigating:{label}')

        # Send goal in a thread so we don't block the mic/topic listener
        nav_thread = threading.Thread(
            target=self._navigate_and_return,
            args=(x, y, yaw, label),
            daemon=True,
        )
        nav_thread.start()

    def _handle_navigate_home(self):
        if self.is_navigating:
            speak('Cancelling current trip. Returning home.', self.get_logger())
            self._cancel_current_goal()
            time.sleep(0.5)
        else:
            speak('Returning home.', self.get_logger())

        self.publish_status('navigating:HOME')
        nav_thread = threading.Thread(
            target=self._navigate_to_point,
            args=(HOME[0], HOME[1], HOME[2], 'HOME', False),
            daemon=True,
        )
        nav_thread.start()

    def _handle_stop(self):
        if self.is_navigating:
            self._cancel_current_goal()
            speak('Navigation cancelled.', self.get_logger())
            self.publish_status('stopped')
        else:
            speak('I am not navigating right now.', self.get_logger())

    def _handle_list(self):
        depts = ', '.join(sorted(DEPARTMENTS.keys()))
        speak(f'I can go to these departments: {depts}. '
              f'I also know {len(DOCTORS)} doctors and {len(ROOMS)} rooms.',
              self.get_logger())

    def _handle_status(self):
        if self.is_navigating:
            speak(f'I am heading to {self.current_label}.', self.get_logger())
        else:
            speak('I am idle at my current position.', self.get_logger())

    # ── Nav2 goal sending ──

    def _navigate_and_return(self, x, y, yaw, label):
        """Navigate to target, wait, then return home."""
        arrived = self._navigate_to_point(x, y, yaw, label, True)

        if arrived:
            speak(f'Arrived at {label}. Waiting {int(self.wait_time)} seconds.', self.get_logger())
            self.publish_status(f'waiting:{label}')
            time.sleep(self.wait_time)

            speak('Returning home.', self.get_logger())
            self.publish_status('navigating:HOME')
            home_arrived = self._navigate_to_point(HOME[0], HOME[1], HOME[2], 'HOME', True)
            if home_arrived:
                speak('I am back home.', self.get_logger())
                self.publish_status('ready')
            else:
                speak('I could not reach home.', self.get_logger())
                self.publish_status('error:home_failed')
        else:
            speak(f'I could not reach {label}.', self.get_logger())
            self.publish_status(f'error:{label}')

    def _navigate_to_point(self, x, y, yaw, label, track=True):
        """Send a single NavigateToPose goal. Returns True if arrived."""
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('Nav2 action server not available!')
            speak('Navigation system is not ready.', self.get_logger())
            return False

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(x)
        goal.pose.pose.position.y = float(y)
        _, _, qz, qw = yaw_to_quaternion(yaw)
        goal.pose.pose.orientation.z = qz
        goal.pose.pose.orientation.w = qw

        self.get_logger().info(f'>> Sending goal: {label} ({x:.1f}, {y:.1f})')

        self.is_navigating = True
        self.current_label = label

        future = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error(f'Goal rejected for {label}')
            self.is_navigating = False
            return False

        self.current_goal_handle = goal_handle
        self.get_logger().info(f'Moving to {label}...')

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        self.is_navigating = False
        self.current_goal_handle = None

        result = result_future.result()
        if result.status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f'Arrived at {label}!')
            return True
        else:
            self.get_logger().warn(f'Failed to reach {label} (status={result.status})')
            return False

    def _cancel_current_goal(self):
        """Cancel the current navigation goal."""
        if self.current_goal_handle is not None:
            self.get_logger().info('Cancelling current goal...')
            cancel_future = self.current_goal_handle.cancel_goal_async()
            rclpy.spin_until_future_complete(self, cancel_future)
            self.is_navigating = False
            self.current_goal_handle = None


def main():
    rclpy.init()
    node = VoiceCommandNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
