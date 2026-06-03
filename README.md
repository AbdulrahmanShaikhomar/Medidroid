# MediDroid

An autonomous differential-drive hospital delivery robot built on a Raspberry Pi 5
with ROS 2 Jazzy. MediDroid combines LiDAR SLAM/Nav2 navigation, IMU-fused heading,
an ESP32 motor controller, and a local voice command subsystem so staff can send it
to rooms by voice.

This repository is a full snapshot of the on-robot project: ROS 2 workspace, standalone
nodes, saved maps, the voice subsystem, and the engineering notes accumulated while
building it.

## Hardware

- **Compute:** Raspberry Pi 5 (Ubuntu 24.04 LTS, ROS 2 Jazzy)
- **Motor controller:** ESP32 (serial `M,left,right` PWM protocol)
- **Drive:** 4x DC motors w/ encoders, 2x IBT_2 H-bridges, differential drive
- **LiDAR:** RPLIDAR C1
- **IMU:** MPU-9255 (gyro-Z used for heading, fused via EKF)
- **Power:** 12V battery → buck converter → 5V Pi/ESP32

## Repository layout

| Path | What it is |
|------|------------|
| `ros2_ws/src/medidroid_base/` | Main ROS 2 package: `safety_gate`, `esp32_driver`, `obstacle_detector`, teleop, route/voice nodes, Nav2 params, launch files |
| `ros2_ws/src/sllidar_ros2/`, `rf2o_laser_odometry/` | Third-party LiDAR driver + laser odometry (vendored sources) |
| `imu_mpu9255_node.py` | Standalone IMU node → `/imu/data_raw` @ 100 Hz with continuous bias tracking |
| `webdrive.py` | HTTP teleop + route record/replay server (the validated motion path) |
| `ekf.yaml` | robot_localization EKF config (rf2o X/Y + IMU yaw → `odom→base_link`) |
| `voice sub system/` | Local voice agent (faster-whisper STT + edge-tts TTS), hospital DB, route map |
| `*_map.pgm` / `*_map.yaml` | Saved occupancy-grid maps |
| `docs/engineering_memory/` | Detailed engineering notes: navigation tuning, IMU/EKF integration, the safety-gate rewrite, localization debugging |
| `*.py` (home-dir) | Assorted calibration, patch, and diagnostic scripts from development |

## Navigation architecture

- **Heading / rotation:** IMU gyro-Z (authoritative) — fixes rf2o's in-place-rotation blindness
- **Translation X/Y:** LiDAR `rf2o_laser_odometry`
- **Absolute localization:** LiDAR AMCL (`map→odom`); AMCL `alpha1/alpha2 = 0.02` trusts IMU rotation
- **Obstacle avoidance:** Nav2 costmaps + `collision_monitor` + a 360° LiDAR safety zone in `safety_gate`
- **cmd_vel chain:** `controller_server` → `velocity_smoother` → `collision_monitor` → `safety_gate` → ESP32 serial

See `docs/engineering_memory/` for the full reasoning and tuning history.

## Voice subsystem

Fully local/offline-capable speech pipeline (no cloud API keys):

- **STT:** `faster-whisper` (`tiny.en`, cached locally)
- **TTS:** `edge-tts` (free Microsoft Edge voices; needs internet)
- Wake word → command → resolves a doctor/department/room → triggers a recorded
  Nav route via `webdrive.py`

## Notes

- Credentials (SSH password, Wi-Fi keys) referenced in the historical engineering notes
  have been redacted to `<REDACTED_*>` placeholders.
- `build/`, `install/`, virtualenvs, and large binaries are intentionally excluded;
  rebuild the workspace with `colcon build`.

## License

See `LICENSE` files within vendored third-party packages. Project code is released
for open-source use.
