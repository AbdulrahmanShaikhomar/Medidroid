MediDroid Pi Handoff: Hooking Navigation to Voice Interaction
=============================================================

Purpose
-------
This note is for the next person who wants to connect the working Raspberry Pi
voice interaction to the working navigation / motor side.

Current status
--------------
The voice interaction is already doing these things correctly:
- wake word detection
- command recognition
- hospital database lookup
- speed selection (`fast`, `medium`, `easy`)
- spoken reply through the USB speaker

The navigation side is already doing these things correctly on its own:
- LiDAR startup
- SLAM / odometry stack
- `/cmd_vel` -> ESP32 PWM bridge
- ESP32 serial communication

What is NOT connected yet:
- the voice interaction does NOT send a real ROS2 nav goal yet
- the speed selection does NOT change the live nav controller yet

Right now the voice agent only prints:
- `[ESP32 SPEED TARGET] ...`
- `[ROS2 BRIDGE] PUBLISHING NAV GOAL: {x: ..., y: ..., z: 0.0}`


Main files to know
------------------
Voice side:
- `voice_system/agent_raspberry_pi.py`
- `voice_system/hospital_db.json`

Nav / robot side on the Pi:
- `~/start_robot.sh`
- `~/fixed_launch.py`
- `~/ros2_ws/src/medidroid_base/medidroid_base/safety_gate.py`
- `~/ros2_ws/src/medidroid_base/medidroid_base/esp32_driver.py`


Current voice integration point
-------------------------------
The ONLY function that should be treated as the main hook point is:
- `publish_nav_goal()` inside `voice_system/agent_raspberry_pi.py`

That function is called only after:
1. a valid destination is found
2. the user selects speed

So by the time `publish_nav_goal()` runs, the voice side has already decided:
- which destination to go to
- which speed profile to use

The current speed profiles are:
- `fast` -> internal profile `fastest` -> PWM `255`
- `medium` -> internal profile `normal` -> PWM `170`
- `easy` -> internal profile `slow` -> PWM `85`


Recommended integration strategy
--------------------------------
Do NOT rewrite the voice logic.
Do NOT touch wake-word handling, speech timing, or database matching unless needed.

The clean approach is:

1. Keep the voice agent responsible for:
- destination recognition
- doctor / department lookup
- speed selection

2. Replace the body of `publish_nav_goal()` with a real bridge that:
- publishes or sends the target coordinates
- passes the chosen speed profile to the movement side

3. Leave the nav stack responsible for:
- path planning
- obstacle avoidance
- motor control


Best practical architecture
---------------------------
Option A: Proper ROS2 integration (recommended)
- voice agent sends a real Nav2 goal to the ROS2 stack
- voice agent also sends the selected speed profile to a small ROS2 topic or helper node
- nav stack keeps generating `/cmd_vel`
- `safety_gate.py` keeps converting `/cmd_vel` to ESP32 serial PWM

Why this is best:
- keeps responsibilities clean
- avoids fighting the existing navigation pipeline
- uses the stack that already exists


Option B: Direct serial speed override + ROS2 nav goal
- voice agent sends nav goal into ROS2
- voice agent separately sends the selected PWM preference somewhere simple
- motor bridge or helper node applies that preference while the robot is moving


What the current nav side already expects
-----------------------------------------
From `safety_gate.py`:
- listens to `/cmd_vel`
- writes to ESP32 serial at:
  - `/dev/ttyESP32`
  - `115200` baud
- command format:
  - `M,left_pwm,right_pwm`

Important constants in `safety_gate.py`:
- `MIN_PWM = 90`
- `LINEAR_SCALE = 600.0`
- `ANGULAR_SCALE = 300.0`
- `LEFT_MOTOR_BOOST = 1.10`

This means the live motor output is already controlled downstream from `/cmd_vel`.
So the voice side should preferably avoid writing motor commands directly unless the
whole navigation chain is intentionally bypassed.


Current LiDAR / stack notes
---------------------------
From `start_robot.sh` and `fixed_launch.py`:
- LiDAR is using `/dev/ttyUSB1`
- the ESP32 serial bridge is separate
- `slam_toolbox` and the transform chain are already part of the robot startup

This matters because the voice side should NOT guess serial devices.
The voice side should pass high-level intent only:
- destination coordinates
- speed preference


How to map the voice DB to navigation
-------------------------------------
The destination coordinates are already stored in:
- `voice_system/hospital_db.json`

For doctor requests:
- each doctor office already has `coordinates`

For department requests:
- each department now has top-level `coordinates`
- `Emergency` is hallway-only and uses its own department-level coordinates

So the database is already ready for nav hookup.


What to change first
--------------------
If someone is starting this integration later, do it in this order:

1. Start the robot stack normally and confirm nav works without voice.

2. In `agent_raspberry_pi.py`, edit only `publish_nav_goal()` first.

3. Replace the current print-only behavior with a real bridge:
- either ROS2 action / topic publish
- or a helper script / node call

4. Keep the existing log prints at first.
They are useful while debugging:
- `[ESP32 SPEED TARGET] ...`
- `[ROS2 BRIDGE] PUBLISHING NAV GOAL ...`

5. After the nav hookup works, then optionally clean up logs.


What NOT to break
-----------------
Avoid changing these unless absolutely necessary:
- wake-word detection
- `listen()`
- response-time logging
- prompt beep
- speed-selection dialogue
- database alias matching

Those parts are already tuned and validated for the report/demo.


Simple integration target
-------------------------
A good first finished behavior is:

1. User says:
   `Where is dr ahmed?`

2. Voice system says:
   `I have located Dr. Tariq Ahmed Al-Farsi... What speed would you like: fast, medium, or easy?`

3. User says:
   `medium`

4. Voice system sends:
- destination coordinates for Dr. Tariq Ahmed Al-Farsi
- speed profile `normal` / PWM target `170`

5. Nav stack begins real movement.


Final note
----------
The voice interaction side is already in a strong state.
The safest path is to treat it as a stable front-end and connect the nav system
through the existing `publish_nav_goal()` handoff point instead of redesigning the
conversation flow.
