"""
MediDroid Voice Listener - Microphone to /voice_text
====================================================

Lightweight node: listens on USB microphone via Vosk (offline STT),
publishes recognized text to /voice_text topic.

route_executor subscribes to /voice_text and handles navigation.

Requirements:
  pip install vosk pyaudio
  sudo apt install flite portaudio19-dev
  # Download Vosk model (one time):
  cd ~ && wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
  unzip vosk-model-small-en-us-0.15.zip

If no microphone / no Vosk model, you can still send commands manually:
  ros2 topic pub --once /voice_text std_msgs/String "data: go to cardiology"
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json
import os
import threading
import time
import subprocess


VOSK_MODEL_PATHS = [
    os.path.expanduser('~/vosk-model-small-en-us-0.15'),
    os.path.expanduser('~/vosk-model'),
    '/opt/vosk/model',
]

SAMPLE_RATE = 16000
CHUNK_SIZE = 4000  # ~250ms at 16kHz


def speak(text, logger=None):
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


class VoiceListener(Node):
    def __init__(self):
        super().__init__('voice_listener')

        self.declare_parameter('model_path', '')
        self.declare_parameter('wake_word', '')       # empty = always listening
        self.declare_parameter('wake_timeout', 8.0)   # seconds after wake word

        self.model_path = self.get_parameter('model_path').get_parameter_value().string_value
        self.wake_word = self.get_parameter('wake_word').get_parameter_value().string_value.lower()
        self.wake_timeout = self.get_parameter('wake_timeout').get_parameter_value().double_value

        self.text_pub = self.create_publisher(String, '/voice_text', 10)

        self.get_logger().info('Voice listener starting...')
        if self.wake_word:
            self.get_logger().info(f'Wake word: "{self.wake_word}"')
        else:
            self.get_logger().info('No wake word - always listening')

        threading.Thread(target=self._mic_loop, daemon=True).start()

    def _find_model(self):
        if self.model_path and os.path.isdir(self.model_path):
            return self.model_path
        for path in VOSK_MODEL_PATHS:
            if os.path.isdir(path):
                return path
        return None

    def _mic_loop(self):
        try:
            import vosk
            import pyaudio
        except ImportError as e:
            self.get_logger().error(f'Missing dependency: {e}')
            self.get_logger().info('Install: pip install vosk pyaudio')
            self.get_logger().info('Manual commands still work:')
            self.get_logger().info('  ros2 topic pub --once /voice_text std_msgs/String "data: go to demo"')
            return

        model_path = self._find_model()
        if not model_path:
            self.get_logger().error(
                'Vosk model not found! Download it:\n'
                '  cd ~\n'
                '  wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip\n'
                '  unzip vosk-model-small-en-us-0.15.zip'
            )
            self.get_logger().info('Manual commands via /voice_text topic still work')
            return

        self.get_logger().info(f'Loading model from {model_path}...')
        model = vosk.Model(model_path)
        rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        rec.SetWords(True)

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
            self.get_logger().error(f'Microphone error: {e}')
            self.get_logger().info('Is a USB microphone connected?')
            pa.terminate()
            return

        self.get_logger().info('Microphone active - listening for commands')
        speak('Voice control ready', self.get_logger())

        # Wake word state
        wake_active = not bool(self.wake_word)
        wake_expire = 0.0

        while rclpy.ok():
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                time.sleep(0.1)
                continue

            if not rec.AcceptWaveform(data):
                continue

            result = json.loads(rec.Result())
            text = result.get('text', '').strip()
            if not text:
                continue

            self.get_logger().info(f'Heard: "{text}"')

            # Wake word gating
            if self.wake_word:
                if not wake_active:
                    if self.wake_word in text.lower():
                        wake_active = True
                        wake_expire = time.time() + self.wake_timeout
                        speak('Yes? What would you like?', self.get_logger())
                        self.get_logger().info('Wake word detected - listening...')

                        # If the wake word sentence also has a command, extract it
                        # e.g. "medidroid go to cardiology"
                        idx = text.lower().find(self.wake_word)
                        after = text[idx + len(self.wake_word):].strip()
                        if len(after) > 3:
                            msg = String()
                            msg.data = after
                            self.text_pub.publish(msg)
                            self.get_logger().info(f'Published: "{after}"')
                            wake_active = False
                    continue

                if time.time() > wake_expire:
                    wake_active = False
                    self.get_logger().info('Wake timeout - sleeping')
                    continue

            # Publish recognized text
            msg = String()
            msg.data = text
            self.text_pub.publish(msg)
            self.get_logger().info(f'Published: "{text}"')

            if self.wake_word:
                wake_active = False

        stream.stop_stream()
        stream.close()
        pa.terminate()


def main():
    rclpy.init()
    node = VoiceListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
