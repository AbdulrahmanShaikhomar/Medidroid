
import subprocess
import time

try:
    proc = subprocess.Popen(
        ['bash', '-c', 'source /opt/ros/jazzy/setup.bash && source /home/medidroid/ros2_ws/install/setup.bash && ros2 run medidroid_base safety_gate'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    time.sleep(8)
    proc.terminate()
    try:
        stdout, _ = proc.communicate(timeout=3)
        print(stdout[-3000:] if len(stdout) > 3000 else stdout)
    except:
        proc.kill()
        print("Killed")
except Exception as e:
    print(e)
