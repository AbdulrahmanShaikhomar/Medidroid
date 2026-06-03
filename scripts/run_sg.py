
import subprocess
import time

try:
    proc = subprocess.Popen(['bash', '-c', 'source /opt/ros/jazzy/setup.bash && source /home/medidroid/ros2_ws/install/setup.bash && ros2 run medidroid_base safety_gate'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(5)
    proc.terminate()
    stdout, stderr = proc.communicate(timeout=2)
    print("STDOUT:")
    print(stdout)
    print("STDERR:")
    print(stderr)
except Exception as e:
    print(e)
