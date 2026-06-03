---
name: MediDroid Robot Project
description: Full architecture and Pi state for the MediDroid autonomous robot project
type: project
originSessionId: dfb8b7cb-f0a2-4abd-9827-782b59255e7c
---
# MediDroid Robot - Project Overview

MediDroid is a 4-wheel differential drive autonomous robot built for SLAM + Nav2 navigation.

## Hardware
- **Main controller**: Raspberry Pi 5 (Ubuntu 24.04 LTS, ROS 2 Jazzy)
- **Motor controller**: ESP32 (firmware: esp32_encoder_drive.ino or esp32_proportional_drive.ino)
- **Motor drivers**: 2x IBT_2 H-bridge (12V, one per side)
- **Motors**: 4x DC motors with encoders (330 ticks/rev, radius 0.0325m, wheelbase 0.15m)
- **LiDAR**: RPLIDAR C1
- **Power**: 12V 9A battery → buck converter → 5V for Pi+ESP32

## Pi Connection
- Hostname: `raspberrypi.local`
- IP: `10.42.0.1` (Pi runs WiFi AP on the BUILT-IN radio). **AP SSID = `Medidroid`, PSK = `<REDACTED_AP_PSK>`** (NM profile name is "MyHotspot", ipv4=shared → 10.42.0.1, DHCP 10.42.0.10-254).
- SSH: `ssh medidroid@raspberrypi.local` (or `@10.42.0.1`) password: `<REDACTED_SSH_PASSWORD>`
- **Interface-rename gotcha (2026-06-01):** after a reboot the built-in radio may come up as `wlan1` instead of `wlan0` (USB dongle grabs enum order). The MyHotspot AP profile was hard-pinned to `interface-name=wlan0` → silently failed. FIX: rebound it to the built-in **by MAC** `88:a2:9e:4d:0f:68` and cleared interface-name, so it binds the right radio regardless of wlanN numbering. `autoconnect=yes`, priority 10 → comes back every boot. Built-in = brcmfmac/phy0; dongle = `wlx98ba5ffdf853`/rtl88XXau/phy2 (MAC 98:ba:5f:fd:f8:53).
- eth0 is DOWN; reach Pi via the `Medidroid` AP (10.42.0.1) or via dongle on the upstream LAN (raspberrypi.local ≈ 192.168.1.186).

## Internet / WiFi dongle (added 2026-05-31)
The Pi gives internet UNTETHERED via a USB WiFi dongle, separate from the control AP.
- **Control link (unchanged):** `wlan0` = AP "MyHotspot" at `10.42.0.1` — the laptop connects here to reach the Pi. NEVER repurpose wlan0; activating a client profile on it kills SSH.
- **Internet dongle:** TP-Link Archer T2U Nano, USB `2357:011f`, chip **RTL8821AU**. Enumerates as `wlx98ba5ffdf853` (was wlan1). **Driver gotcha:** this ID is NOT 88x2bu/RTL8812BU — the working driver is **aircrack-ng/rtl8812au** (`driver_info=RTL8821`). Built via DKMS (`8812au/5.6.4.2`, module `88XXau`), source in `/home/medidroid/rtl8812au` with Makefile platform flipped to `CONFIG_PLATFORM_ARM64_RPI=y` (I386_PC=n). DKMS-installed → auto-loads on boot/kernel update.
- **Connected to `<REDACTED_WIFI_SSID>`** (2.4GHz; the 5G SSID is out of range from the robot's spot, only 2.4G scans). PSK `<REDACTED_WIFI_PSK>` (same router as 5G). `autoconnect=yes`.
- **Routing/failover:** eth0 wired = primary (metric 100) when plugged; dongle = backup default (metric 601) → auto-failover when cable unplugged. router `192.168.1.1`; eth0≈`.233`, dongle≈`.186` (DHCP, both same subnet).
- **Multi-home fix:** eth0+dongle share 192.168.1.0/24 → set `rp_filter=2` (loose), persisted in `/etc/sysctl.d/99-multihome-rpfilter.conf` (else apps bound to dongle IP see false 100% loss).
- **sudo:** needs password; non-interactive via `echo '<REDACTED_SSH_PASSWORD>' | sudo -S ...`.

## USB / udev
- `/dev/ttyUSB0` and `/dev/ttyUSB1` present
- udev symlinks in `/etc/udev/rules.d/99-robot-usb.rules`:
  - `CP2102` → `/dev/ttyESP32` (motor controller)
  - `CP2102N` → `/dev/ttyLIDAR` (LiDAR)

## Pi ROS2 Workspace (`~/ros2_ws/src/`)
- `medidroid_base` — main ROS2 package (Python)
- `sllidar_ros2` — RPLIDAR C1 driver (cloned)
- `rf2o_laser_odometry` — LiDAR-only odometry (cloned, C++) — alternative to wheel encoders

## ROS2 Nodes (medidroid_base)
- `esp32_driver.py` — cmd_vel → serial → ESP32, reads encoder ticks, publishes odom
- `safety_gate.py` — /cmd_vel → ESP32 serial bridge + 360° LiDAR collision safety + watchdog (REWRITTEN 2026-06-02 — see "safety_gate.py — motion-output node" below)
- `wasd_teleop.py` — WASD keyboard → /cmd_vel
- `obstacle_detector.py` — LiDAR obstacle warnings

## Maps saved on Pi
- `~/basement_map` — large map (2.2MB pgm), origin [-46.9, -5.5]
- `~/basement1_map` — refined basement map (1.7MB pgm)
- `~/my_home_map` — most recent (Apr 29 2026, 12KB pgm, small area), origin [-2.9, -3.2]

## Confirmed Working Workflows

### Mapping (4 terminals)
```
T1: ros2 launch /home/medidroid/ros2_ws/src/nav_hardware_launch.py   # LiDAR + static TF
T2: ros2 run medidroid_base safety_gate                               # motors + encoder odom
T3: ros2 launch /home/medidroid/ros2_ws/src/slam_launch.py           # SLAM Toolbox
T4: export LIBGL_ALWAYS_SOFTWARE=1 && rviz2                           # visualization
```

### Save map
```
ros2 run nav2_map_server map_saver_cli -f ~/my_home_map
```

### Navigation (user's verbatim 4-terminal flow — T1 is now canonical IMU-fused)
```
T1: ros2 launch /home/medidroid/ros2_ws/src/nav_hardware_launch.py        # LiDAR+TF+rf2o(publish_tf=False)+IMU+EKF
T2: ros2 run medidroid_base safety_gate                                    # /cmd_vel → ESP32 (sustained pivots)
T3: ros2 launch medidroid_base nav_launch.py map:=/home/medidroid/mapp.yaml  # Nav2 + pose_manager
T4: export LIBGL_ALWAYS_SOFTWARE=1 && rviz2                                # visualization
```

## Launch Files
- `~/start_robot.sh` — simple bash: kills old procs, starts LiDAR on ttyUSB1, static TF, SLAM
- `~/ros2_ws/src/medidroid_base/launch/nav_launch.py` — full Nav2 stack using my_home_map.yaml
- `~/ros2_ws/src/slam_launch.py` — SLAM mapping launch (user-confirmed, contents unknown)
- `~/ros2_ws/src/mapping_launch.py` — LiDAR + rf2o odometry + static TF + SLAM
- `~/ros2_ws/src/my_robot_launch.py` — LiDAR + SLAM + lifecycle manager (no motor driver)
- `~/ros2_ws/src/nav_hardware_launch.py` — LiDAR on /dev/ttyLIDAR + static TF only

## webdrive.py — LIVE control server (the real motion path, validated 2026-06-01)
`/home/medidroid/webdrive.py` is a standalone rclpy Node + ThreadingHTTPServer on **0.0.0.0:8080**. It IS the implementation of the validated motion primitives (`drive()`=rf2o-yaw closed loop, `turn()`=LiDAR x-correlation). NOT route_executor.py — that file does NOT exist on the Pi.
- Opens `/dev/ttyESP32` @115200 with `exclusive=True` (refuses to share tty with safety_gate → prevents the M,0,0 watchdog-stutter trap). **Won't start if ESP32 absent.**
- Subscribes `/odom` (rf2o) + `/scan`; sends `M,left,right\n` PWM to ESP32. Caps: MAX_PWM=150, MIN_PWM=55, RBAL=0.82 (right-wheel scale). Replay drive uses FIXED DRIVE_L0=100/DRIVE_R0=82; turn uses ±150/±110.
- **HTTP API (all GET):** `/cmd?x=&y=` teleop joystick · `/stop` abort · `/speed?v=55..150` (teleop only — replay ignores it) · `/rec_start?name=` / `/rec_stop` record route → `/home/medidroid/routes/<name>.csv` (captures rf2o poses) · `/routes` JSON list · `/run?name=&mode=there|back|full` replay (there=go, full=go+spin360+back) · `/diag` · `/status`. Web UI at `/`.
- Routes are translate-only anchored (start→robot pos) then bearing-corrected per waypoint; obstacle pause <0.30m / resume >0.40m built in.
- Saved routes on disk: **roomA, roomB, roomC** (only 3 exist).
- **Voice "when to speak" panel (added 2026-06-01):** webdrive serves a live monitor on its web UI for when there's no speaker. Added GET `/voice_log` (tails last ~8KB / 40 lines of `/tmp/agent.log`, returns `{"lines":[...]}` JSON) + a "Voice agent — when to speak" panel (`#vcue` cue banner + `#vlog` scroll) that polls it every 1s and classifies the latest marker → SAY hey medidroid / SPEAK NOW / thinking / ROBOT MOVING-mic locked / back home. Display-only; no serial/replay changes. Backup: `webdrive.py.bak_prevoiceui`. NOTE: only restart webdrive when `/status` mode==teleop (the deploy script self-aborts if mid-replay).
- **roomC FULL live test PASSED (2026-06-01):** voice "take me to room C" → roomC replay ran THERE→SPIN360→BACK 17/17 → RUN DONE, robot returned to start, mic auto-unlocked. End-to-end voice→nav→home confirmed with real motion.

## Voice → Navigation wiring (implemented + dry-run validated 2026-06-01)
Voice bundle at `/home/medidroid/voice sub system/raspberry_pi_bundle/` (spaces in path; alias `voice_sub_system`). venv Python 3.12.3, ALL deps present (edge_tts, speech_recognition, faster_whisper, pyaudio, numpy). STT=faster_whisper tiny.en (cached). TTS=edge_tts en-US-AriaNeural (needs internet — dongle provides it). Mic=K66 USB **index 0 / hw:2,0 / plughw:2,0** (also the auto-selected USB playback device, but K66 has no speaker — user will add a USB speaker later).
- **agent_raspberry_pi.py `publish_nav_goal()` now triggers webdrive** instead of print-only. Added: `resolve_route_name()` (route_map override → room#/dept slug → validated against live `/routes`), `trigger_webdrive_route()` (urllib GET `/speed` then `/run?name=&mode=there`), `get_live_routes()` (5s cache), `--no-move` dry-run flag. Backup of original at `agent_raspberry_pi.py.bak_prewire`.
- **`voice_system/route_map.json`** maps hospital_db key (room# or dept name, lowercased) → recorded route. Current: 101/cardiology→roomA, 205/neurology→roomB, 301/pediatrics→roomC, **room c/roomc→roomC**. Unmapped destinations → agent speaks "no saved path yet" (graceful).
- **Direct "Room C" destination (added 2026-06-01):** added a department-style entry `"Room C"` to hospital_db.json (offices=[], aliases: room c/roomc/room see/room sea/room cee/...) so the user can say "take me to room C". MUST be FIRST in the departments list — Emergency's alias "emergency room" fuzzy-matches the bare token "room", so whichever comes first wins; Room C first makes it win for "room c". Validated via --no-move dry-run: "take me to room c"/"roomc" → dest "Room C" → route roomC → `/run?name=roomC&mode=full`. Backups: hospital_db.json.bak_preroomc, route_map.json.bak_preroomc.
- process_command matches by DOCTOR NAME or DEPARTMENT (NOT room number); route_key = matched office room (e.g. "101") or dept name.
- Dry-run (`--typed-demo --demo-script X --no-move --mute`) confirmed: "doctor tariq"→roomA, "doctor omar"→roomB, "cardiology"→roomA, "doctor nada"→roomC, "pediatrics"→roomC; correct `/run` URLs; clean "exit".
- **KNOWN LIMITATION:** spoken speed (fast=255/medium=170/easy=85) only hits `/speed` (clamped 55–150) which replay IGNORES → speed is cosmetic during nav. To make real, patch webdrive replay drive() to scale PWM (NOT yet done — needs user OK, motion-affecting).
- **TODO for live test:** power ESP32 (so `/dev/ttyESP32` enumerates — VBUS-cut cable means it only appears when motor board has own power), start webdrive, clear space, user says "go".

## Hardware notes
- USB red wire (VBUS) cut on ESP32 USB cable — data-only connection, no backfeed power

## IMU — MPU9255 (added 2026-06-01)
- **Part:** WHO_AM_I(0x75)=**0x73 → MPU9255** (genuine InvenSense 9-axis: gyro+accel+AK8963 mag; NOT the mag-less 0x70 clone). Register-compatible with all MPU9250 code.
- **Bus:** `/dev/i2c-1` (GPIO2/SDA pin3, GPIO3/SCL pin5), addr **0x68** (AD0 floating). I2C enabled via `dtparam=i2c_arm=on`; user `medidroid` in `i2c` group.
- **Power (FIXED 2026-06-01, was the root cause of bad heading):** VCC now on the **Raspberry Pi 3.3V (pin 1)**, common ground. ORIGINALLY on the **ESP32 3.3V rail** — that BROKE navigation: the instant the motors pulsed, current spikes sagged the ESP rail → **I2C bus corruption → MPU9255 hung (Errno 110, climbing "I2C read errors" in the node log)**. The node kept running but `/imu/data_raw` went silent, so the **EKF coasted on its last yaw-rate → pose rotated steadily while the robot sat still** (user-visible "pose drifts left every few seconds"). Moving VCC to the Pi's regulated 3.3V rail (isolated from motor transients) fixes it: IMU stays at 100 Hz while driving. **NEVER put the IMU back on the ESP rail.** Optional hardening: 10–100 µF bulk cap across IMU VCC/GND.
- **Bias recalibration gotcha:** gyro bias is captured ONCE at node startup and subtracted. After the rewire the bias shifted (~−1.07°/s) and the stale pre-rewire calibration left a residual −1.13°/s → EKF yaw drifted −1.1°/s. FIX = **restart the IMU node (robot still) to recalibrate**; after a fresh cal, rest drift was **0.009°/s** (EKF yaw +0.11° over 12 s — rock steady). Always recalibrate after any power/wiring change. **PERMANENT FIX (2026-06-02):** the node now does CONTINUOUS bias tracking + a rate deadband (see Node entry below) so it self-corrects thermal/time drift in flight — the slow one-way creep no longer needs a manual restart-to-recal.
- **No smbus/smbus2 on the Pi** → all I2C done with **stdlib `fcntl`/`os` ioctl** (I2C_SLAVE=0x0703), like the probe. Nothing to pip-install.
- **Probe tool:** `/tmp/imu_probe.py` (also `C:\Users\abadi\AppData\Local\Temp\imu_probe.py`) — scans i2c-1 0x03–0x77, reads WHO_AM_I at 0x68/0x69.
- **Node:** `/home/medidroid/imu_mpu9255_node.py` — standalone rclpy node (matches webdrive pattern, NOT a colcon entry point). Publishes **`sensor_msgs/Imu` on `/imu/data_raw` @ 100 Hz**, frame `imu_link`. Config: gyro ±500 dps (65.5 LSB/°·s⁻¹), accel ±2 g (16384 LSB/g), DLPF ~41 Hz, SMPLRT_DIV=9. **Startup gyro-bias calibration** (robot MUST be still ~1.5 s at launch). `orientation_covariance[0]=-1` (no orientation estimate — feed madgwick or integrate gyro-Z). Source also at `C:\Users\abadi\AppData\Local\Temp\imu_mpu9255_node.py`. **DRIFT FIX (2026-06-02, deployed):** added two things in `tick()` — (1) **continuous gyro-bias tracking**: when not rotating (every axis `|rate|<STILL_THRESH=0.8°/s` sustained `STILL_WIN=50` samples ≈0.5 s) the per-axis bias EMA-tracks the live reading (`BIAS_ALPHA=0.002`, clamped `±BIAS_CLAMP=5°/s`) to chase thermal drift; freezes automatically during real turns. (2) **rate DEADBAND=0.6°/s**: after bias removal, `|corrected rate|<0.6°/s → exactly 0.0` so sub-threshold residual/noise never integrates into EKF yaw. Real Nav2 turns (`rotate_to_heading`≈1.0 rad/s=57°/s) are ~90× above the band → untouched; gate's own `TURN_W_MIN=0.05 rad/s` floor sits above the band too → no settle-stall. Module-level `_clamp(v,lim)` helper added; `self.bias` is now a 3-list (was tuple). Logs `gyro bias est (deg/s): … still_cnt=N` every ~15 s (1500 ticks) so you can watch it track. Single copy on Pi (`/home/medidroid/imu_mpu9255_node.py`, launched via ExecuteProcess from every hardware-launch) — one push covers all T1 variants. py_compile OK on Pi. **VERIFY:** restart T1 (robot dead-still for the startup cal) → run `python3 /home/medidroid/yaw_meas.py` → cumDyaw must hold flat at rest (no +0.1°/few-sec creep).
- **Run:** `bash -c 'source /opt/ros/jazzy/setup.bash; source ~/ros2_ws/install/setup.bash; python3 /home/medidroid/imu_mpu9255_node.py'`
- **Validated 2026-06-01:** 100.01 Hz stable, gyro ≈0 at rest (z=0.027°/s after bias), accel |g|=8.69 m/s² (reads ~0.886 g — typical cheap-IMU scale error; harmless: we use gyro for yaw, madgwick normalizes accel direction; trim ×1.13 only if accel magnitude is ever used).
- **Why it matters / next step:** rf2o is BLIND to in-place rotation (see [[motion-primitives]]); the **gyro-Z directly measures turn rate** → the right fix for `turn(deg)` (replace/augment the slow LiDAR-xcorr). Planned Stage 2: webdrive subscribes `/imu/data_raw`, integrates gyro-Z for turns. NOT yet done (motion-affecting → needs user OK + clear-space + "go").

## IMU→EKF→Nav2 integration (VALIDATED structurally 2026-06-01, no-motion)
- **EKF (robot_localization `ekf_node`):** config `/home/medidroid/ekf.yaml` (node key `ekf_filter_node`), freq 30 Hz, `two_d_mode:true`, `publish_tf:true`, world=odom. Fuses **`/odom` (rf2o) X,Y translation** + **`/imu/data_raw` vyaw (gyro-Z, config idx 11)** → owns **`odom→base_link`** TF + `/odometry/filtered`. rf2o runs with **publish_tf=False** (EKF owns the TF). This fixes rf2o's in-place-rotation blindness.
- **Bringup launch — ALL VARIANTS UNIFIED to canonical IMU-fused config (2026-06-02):** the user's 4-terminal flow uses `T1: ros2 launch /home/medidroid/ros2_ws/src/nav_hardware_launch.py`. That file (and ALL 5 hardware-launch variants on the Pi: nav_hardware_launch.py, imu_hardware_launch.py, mapping_launch.py, my_robot_launch.py + the src copies) were OVERWRITTEN with one canonical body so whichever T1 the user runs is identical and IMU-fused. Canonical body starts: sllidar(/dev/ttyLIDAR 460800, frame laser) + static base_link→laser `0.1 0 0.2 3.14159 0 0` (π yaw, backward LiDAR — DO NOT CHANGE) + static base_link→imu_link `0 0 0.1 0 0 0` (identity rot; X-fwd Y-left Z-up) + rf2o(odom_topic=/odom, **publish_tf=False**, freq=10) + ExecuteProcess `python3 -u /home/medidroid/imu_mpu9255_node.py` + ekf_node(name `ekf_filter_node`, params /home/medidroid/ekf.yaml). **Single odom→base_link publisher (EKF only)** — rf2o's publish_tf=False removes the rotation-blind double-TF footgun. Local canonical copy `C:\Users\abadi\AppData\Local\Temp\pi\canonical_hardware_launch.py`; per-file backups `*.bak_<ts>` on Pi.
- **Nav2 layers on top, no conflict:** `ros2 launch medidroid_base nav_launch.py` = nav2_bringup (all nodes **composed in one `component_container_isolated`** → `pgrep amcl` shows nothing; use `ros2 lifecycle get /amcl`) + `pose_manager`. AMCL `set_initial_pose:true` seed (-0.46,1.15,-1.60rad) BUT **`pose_manager` restores last pose from `~/.ros/medidroid_last_pose.yaml`** which OVERRIDES the seed → AMCL starts wherever last parked. AMCL `DifferentialMotionModel` consumes the EKF odom→base_link delta (so IMU rotation now feeds AMCL's motion model). `scan_topic: scan`.
- **Verified 2026-06-01 (at rest, no motion):** all lifecycle nodes `active`; full TF chain map→odom(AMCL)→base_link(EKF)→laser resolves; `/amcl_pose` + both costmaps publishing; EKF heading drift ≈0.014°/s at rest (startup bias-cal good). odom yaw is allowed to drift; AMCL map→odom corrects absolute.
- **STILL PENDING (needs user):** (1) rotation-tracking demo — hand-rotate ~90°, expect EKF/IMU yaw ~+90° vs rf2o raw ~10-20° (non-motion, safe). (2) autonomous Nav2 goal drive → /cmd_vel → safety_gate → ESP — GATED on user clearing space + "go". (3) confirm AMCL believed pose matches physical reality before any drive (else re-seed via /initialpose or 2D Pose Estimate).
- **Watcher tool:** `C:\Users\abadi\AppData\Local\Temp\yaw_watch.py` (→ /tmp) prints EKF/IMU yaw vs rf2o raw yaw side-by-side; `run_yawwatch.py` deploys+runs it.

## safety_gate.py — motion-output node (REWRITTEN 2026-06-02)
THE last hop of the cmd_vel chain: `/cmd_vel` → safety_gate → `M,left,right\n` serial → ESP32. Class `DiffDriveBridge('safety_gate')`. Local copy `C:\Users\abadi\AppData\Local\Temp\pi\safety_gate.py`.
- **Deploy = COPY to BOTH paths (install is NOT --symlink-install):** edits must land in `src/medidroid_base/medidroid_base/safety_gate.py` AND `install/medidroid_base/lib/python3.12/site-packages/medidroid_base/safety_gate.py` (a real 13KB file — that install copy is what `ros2 run` executes), then clear BOTH `__pycache__/safety_gate*`. Same dual-deploy rule applies to any colcon node. Deploy script `C:\Users\abadi\AppData\Local\Temp\redeploy_gate.py`. Backups `safety_gate.py.bak_<ts>` on Pi (src+install).
- **SUSTAINED proportional in-place pivot (replaced the old 50 ms pulse hack):** when `|v|<TURN_V_MAX(0.03)` and `|w|>TURN_W_MIN(0.05)` → `frac=min(1,|w|/TURN_W_REF(1.0))`, `mag=int(120 + (150−120)*frac)` (TURN_PWM_MIN=120, TURN_PWM_MAX=150), then `_send(-mag,+mag)` for w>0 (CCW/LEFT) or `_send(+mag,-mag)` for w<0 (CW/RIGHT) — held continuously, NOT pulsed. **Why safe now:** the old pulse hack existed to keep rf2o (rotation-BLIND) from runaway open-loop spins; the IMU gyro-Z now feeds true yaw into EKF→AMCL, closing the loop, so a sustained pivot is observed and corrected. `w=msg.angular.z` (NO negation; +z=LEFT/CCW).
- **RIGHT_SCALE = 0.82** (was 0.80) — matches webdrive RBAL hand-calibrated right-wheel balance. `_send` applies RIGHT_SCALE, bumps any non-zero below MIN_PWM(55) up to MIN_PWM (deadzone), clamps to MAX_PWM(150). Validated pivot `_send(-130,+130)` → emits `M,-130,106`.
- **Clean shutdown:** `main()` catches `except (KeyboardInterrupt, ExternalShutdownException): pass` (import from `rclpy.executors`) so Ctrl-C / `timeout` kill exits with NO traceback; `finally` still runs `node.stop_motors()` (`M,0,0`). Load-verified: gate reaches "safety_gate ready", subscribes /cmd_vel, CLEAN EXIT.
- **UNCHANGED/preserved:** WHEEL_BASE=0.34, MAX_VEL=0.20, MAX_PWM=150, MIN_PWM=55; 360° LiDAR safety zones/arcs in `_on_scan`; watchdog (0.25 s timer → `M,0,0` if no /cmd_vel for >0.5 s); `_drain_serial` thread (discards ESP `E,left,right` telemetry); diff-drive arc kinematics for travel (v_left=v−w·WB/2, v_right=v+w·WB/2). ESP firmware watchdog is DISABLED → the gate's `finally` hard-stop is the only stop guarantee.

## cmd_vel chain — verified CLEAN, no blocking/parallel drive (2026-06-02)
`controller_server`/`behavior_server` → `/cmd_vel_nav` → `velocity_smoother` → `/cmd_vel_smoothed` → `collision_monitor` → `/cmd_vel` → `safety_gate`. The TWO publishers on `/cmd_vel` are `collision_monitor` (real, the live source) + `docking_server` (DORMANT — only publishes during an active docking action, never during normal nav). **No double-drive, no parallel writers to the ESP.** velocity_smoother max [0.18, 0, 1.2]; collision_monitor cmd_vel_in=cmd_vel_smoothed, cmd_vel_out=cmd_vel.

## IMU-vs-LiDAR for movement — design conclusion (2026-06-02)
User asked whether to rely on IMU instead of LiDAR for movement. **An IMU CANNOT measure translation/position** — accelerometer double-integration drifts to meters of error in seconds — it only measures ROTATION (gyro). So "IMU for all movement" is physically impossible. **Optimal split (now implemented):** Heading/rotation → **IMU gyro** (authoritative, fixes rf2o rotation-blindness); Translation X/Y → **LiDAR rf2o** (only available position source); Obstacle avoidance → **LiDAR** (costmaps + collision_monitor + gate zones); Absolute localization → **LiDAR AMCL**. The user's intuition is right in spirit — the IMU (not rotation-blind LiDAR odom) is now the turning authority. **FUTURE upgrade matching their full vision:** wheel-encoder odometry from ESP `E,left,right` telemetry (esp32_driver.py shows ticks_per_rev≈330, wheel_radius≈0.0325 m) fused with IMU yaw to demote LiDAR to avoidance-only — requires ESP up + ticks/meter calibration; NOT bolted in now (won't ship untested odometry).

## .bashrc ROS sourcing
```
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash
```

## Last activity (Apr 29 2026)
- colcon build completed at 00:59
- ran `ros2 run medidroid_base safety_gate`
- inspected TF frames (frames_2026-04-29.pdf saved)
- last map saved: my_home_map

**Why:** Tracks current Pi state to avoid re-discovering USB ports, credentials, map names, and package layout each session.
**How to apply:** Use when helping debug, deploy, or extend any robot functionality — know the exact ports, paths, and what's installed.


## Scripted Navigation Calibration (validated 2026-05-29)
Backup plan: timed/scripted nav (Nav2 abandoned). route_executor.py constants:
- TIME_90_LEFT = 2.44 s  (90 deg left turn, validated)
- TIME_90_RIGHT = 2.4 s  (90 deg right turn, validated)
- TURN_VEL = 1.2 rad/s, FULL power (no ramp) - turns need power to beat static friction
- Direction: safety_gate uses w = msg.angular.z (NO negation - earlier negation was a mis-fix; +z=LEFT/CCW, -z=RIGHT/CW)
- CRUISE_SPEED_REAL = 0.225 m/s (measured: 1.3m over 6s fwd_test; dist_test verified 99cm on 1.0m command)
- forward_dist(meters): duration = meters/CRUISE_SPEED_REAL + 0.75*RAMP_TIME (RAMP_TIME=0.3)
- NOTE: safety_gate MAX_VEL=0.20 is mis-scaled (real ~0.45 m/s at MAX_PWM); forward_dist bypasses this via direct cruise measurement
- Test routes: fwd_test (6s fwd), dist_test (1m), left_test, right_test, demo (square)
- No usable odometry/encoders -> open-loop; recalibrate on actual demo floor surface
- STRAIGHT_TRIM = -0.03 rad/s (forward-only yaw bias; robot drifted left, trim steers right; applied in forward_for + forward_until, NOT turns). Tuned: 0=left, -0.06=right, -0.03=straight.
- Obstacle avoidance validated good as-is: _check_obstacle front +/-60deg arc, pause<0.30m, resume>0.40m; safety_gate backstop separate. No tuning needed.
- Test routes added: straight_test (2m), obstacle_test (3m), fwd_test (6s), dist_test (1m).
