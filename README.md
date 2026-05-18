# MediDroid - Autonomous Hospital Navigation Robot

A 4-wheel differential drive autonomous robot for hospital navigation using ROS 2 and Nav2. The robot can navigate to departments, doctor rooms, and specific locations via voice commands or text input.

## Hardware

- **Compute**: Raspberry Pi 5 (Ubuntu 24.04 LTS, ROS 2 Jazzy)
- **Motor Controller**: ESP32 with WiFi AP + Serial bridge
- **Motor Drivers**: 2x IBT_2 H-bridge (12V)
- **Motors**: 4x DC motors with rear encoders
- **LiDAR**: RPLIDAR C1
- **Sensors**: HC-SR04 Ultrasonic, 3x obstacle LEDs
- **Power**: 12V 9A battery with buck converter to 5V

## Repository Structure

```
medidroid_github/
├── esp32/                          # ESP32 motor controller firmware
│   └── esp32claude/
│       ├── esp32claude.ino         # Main firmware (WiFi AP, serial, encoders, ultrasonic)
│       └── drive_mixing.h          # Motor mixing with car-style arc turns
├── ros2_ws/src/
│   ├── medidroid_base/             # Main ROS 2 package
│   │   ├── medidroid_base/
│   │   │   ├── esp32_driver.py     # cmd_vel to ESP32 serial bridge + encoder odom
│   │   │   ├── safety_gate.py      # Motor bridge with decisive mode control
│   │   │   ├── go_to.py            # Hospital waypoint navigator (rooms, departments, doctors)
│   │   │   ├── voice_command.py    # Voice/text command interface (Vosk STT + Nav2)
│   │   │   ├── obstacle_detector.py# LiDAR-based obstacle detection
│   │   │   ├── pose_manager.py     # Pose tracking and management
│   │   │   └── wasd_teleop.py      # Keyboard teleoperation
│   │   ├── launch/
│   │   │   ├── nav_hardware_launch.py  # LiDAR + static TF + rf2o odometry
│   │   │   └── nav_launch.py           # Full Nav2 stack
│   │   ├── config/
│   │   │   └── nav2_params.yaml    # Nav2 config (Regulated Pure Pursuit controller)
│   │   ├── setup.py
│   │   ├── setup.cfg
│   │   └── package.xml
│   ├── mapping_launch.py           # SLAM mapping launch
│   ├── slam_launch.py              # SLAM Toolbox launch
│   ├── slam_params.yaml            # SLAM Toolbox parameters
│   ├── nav_hardware_launch.py      # Hardware launch (standalone)
│   ├── fixed_launch.py             # Fixed frame launch
│   ├── my_robot_launch.py          # Robot launch with lifecycle manager
│   └── pi_motor_driver.py          # Pi-based motor driver (legacy)
├── maps/                           # Map YAML configs (.pgm files excluded)
│   ├── my_home_map.yaml
│   ├── basement_map.yaml
│   └── basement1_map.yaml
└── scripts/
    ├── start_robot.sh              # Quick-start robot script
    └── launch_nav.sh               # Navigation launch script
```

## Hospital Database

The robot knows these locations:

| Department   | Hallway Point | Aliases                            |
|-------------|---------------|-------------------------------------|
| Cardiology  | hall_1        | heart, cardio, cardiac              |
| Neurology   | hall_2        | brain, neuro, nerves                |
| Pediatrics  | hall_3        | children, kids, child clinic        |
| Orthopedics | hall_4        | bones, ortho, joints                |
| Emergency   | hall_5        | er, emergency room, casualty        |

8 doctors across 8 rooms (101, 102, 205, 206, 301, 302, 401, 402) with name aliases.

## Quick Start

### On the Raspberry Pi

```bash
# Terminal 1: Hardware (LiDAR + TF + odometry)
ros2 launch medidroid_base nav_hardware_launch.py

# Terminal 2: Motor bridge
ros2 run medidroid_base safety_gate

# Terminal 3: Navigation stack
ros2 launch medidroid_base nav_launch.py

# Terminal 4: Voice commands
ros2 run medidroid_base voice_command
```

### Voice / Text Commands

```bash
# Via microphone (requires Vosk model):
# "Go to cardiology"
# "Take me to Doctor Tariq"
# "Go home"
# "Stop"

# Via ROS 2 topic:
ros2 topic pub --once /voice_text std_msgs/String "data: go to cardiology"
ros2 topic pub --once /voice_text std_msgs/String "data: take me to doctor tariq"

# Direct waypoint navigation:
ros2 run medidroid_base go_to --ros-args -p target:=cardiology
ros2 run medidroid_base go_to --ros-args -p target:=dr_tariq
ros2 run medidroid_base go_to --ros-args -p target:=room_101
ros2 run medidroid_base go_to --ros-args -p target:=list
```

## Dependencies

### Pi (ROS 2)
- ROS 2 Jazzy
- Nav2
- SLAM Toolbox
- rf2o_laser_odometry
- sllidar_ros2 (RPLIDAR driver)
- pyserial, vosk, pyaudio, flite

### ESP32
- Arduino IDE / PlatformIO
- WiFi, WebServer libraries (built-in)

## Pi Connection

- WiFi Hotspot: `MyHotspot` on wlan0
- SSH: `ssh medidroid@raspberrypi.local`
- IP: `10.42.0.1`

## USB / udev Rules

```
# /etc/udev/rules.d/99-usb-serial.rules
SUBSYSTEM=="tty", ATTRS{product}=="CP2102 USB to UART Bridge Controller", SYMLINK+="ttyESP32"
SUBSYSTEM=="tty", ATTRS{product}=="CP2102N USB to UART Bridge Controller", SYMLINK+="ttyLIDAR"
```
