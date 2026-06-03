---
name: project-motor-dead
description: "DISPROVEN: MediDroid motors are NOT dead. Robot drives fine via WiFi web control AND the full ROS2 stack. Records the real working drive path + why the dead-motor call was wrong."
metadata: 
  node_type: memory
  type: project
  originSessionId: 778036d4-c3b8-44b4-8a3a-67ebe0148485
---

**CORRECTION (2026-05-30): the earlier "motors are physically dead" conclusion was WRONG.** The MediDroid motors / BTS7960 driver / power are **fine**. Proven two ways by the user: (1) the robot drives when commanded through the **ESP32's own WiFi web control** (AP, independent of the Pi serial link); (2) the robot drives through the **full ROS2 stack** (see working path below). Do not chase dead hardware for "won't move."

**The validated drive path (this is THE way to move the robot):**
- T1 — Hardware (LiDAR + odom): `ros2 launch /home/medidroid/ros2_ws/src/nav_hardware_launch.py`
- T2 — Safety gate: `ros2 run medidroid_base safety_gate`
- T3 — Route executor: `ros2 run medidroid_base route_executor`
- Trigger a route: `ros2 topic pub --once /voice_text std_msgs/String "data: go to room 101"`
- Flow: `route_executor` → `/cmd_vel` (Twist) → `safety_gate` → serial `M,l,r` → ESP32. `route_executor` uses timed + LiDAR-assisted scripted moves (forward_dist/turn_left/etc.), NOT Nav2/AMCL/map.

**`room_101` route** (in `route_executor.py` ROUTES) = display "Doctor Abadi Room": announce → forward_dist 2.6 m → turn_left 90° → forward_dist 2.8 m → turn_left 90° → forward_dist 1.0 m → stop. Other built-in test routes: demo, fwd_test, dist_test, straight_test, obstacle_test, left_test, right_test, wall_test.

**Why the dead-motor call was wrong:** the direct-serial `M,l,r` bypass test showed silent motors — but `safety_gate` runs a **0.25 s watchdog that writes `M,0,0`** whenever `/cmd_vel` is idle >0.5 s (`safety_gate.py`). Linux allows two processes to hold `/dev/ttyESP32` at once, so if the gate was running during the bypass test, its `M,0,0` interleaved with the injected `M,200,160` and the motor just stuttered in place (looked dead/silent). Lesson: **do NOT use a raw direct-serial `M,l,r` script as the movement test** — it fights the gate watchdog and the flaky CP2102 link. Use the full stack + a `/voice_text` route command instead.

**Trap — `hardcoded_nav` is NOT installed.** `ros2 run medidroid_base hardcoded_nav` fails with `ModuleNotFoundError: No module named 'medidroid_base.hardcoded_nav'` (the entry-point script exists in install/ but the module was never built in). The real, working node is **`route_executor`**, not `hardcoded_nav`. Ignore `hardcoded_nav.py`.

**Key tuning constants** — `safety_gate.py`: MAX_PWM 150, MIN_PWM 55 (stall floor), RIGHT_SCALE 0.80 (right motor weak), WHEEL_BASE 0.34, MAX_VEL 0.20 m/s, FRONT_STOP 0.30 m. `route_executor.py`: FORWARD_VEL 0.10, TURN_VEL 1.2, TIME_90_LEFT 2.44 s, TIME_90_RIGHT 2.4 s, CRUISE_SPEED_REAL 0.225 m/s, STRAIGHT_TRIM −0.03 (corrects left drift). LiDAR is mounted BACKWARD (yaw=pi): robot front = laser ±pi, rear = 0, left = −pi/2, right = +pi/2.

**UPDATE 2026-05-31 — direct-serial is now the VALIDATED motion path (with the gate stopped).** The old "do NOT use a raw direct-serial `M,l,r` script" warning only holds while `safety_gate` is running (its watchdog `M,0,0` interleaves). With **T2 (safety_gate) Ctrl+C'd**, direct-serial closed-loop primitives drive the robot perfectly — see [[motion-primitives]] (rf2o-yaw `drive`, LiDAR-xcorr `turn`, validated 1m straight + clean 90° turns). Port is exclusive: stop T2 first. The full-stack `/voice_text`→`route_executor` path still exists but the primitive path is what's being built toward room 101.

**Secondary (still true):** ESP32↔Pi USB-serial is intermittently unstable — telemetry framing varies, kernel logs show repeated `cp210x ttyUSB0: failed set request 0x12 status: -110` (control-transfer timeouts). App baud is 115200. Flaky CP2102 cable/connector/power. Related: [[project-nav-fix-plan]], [[project-medidroid]].
