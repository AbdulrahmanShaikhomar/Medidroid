---
name: nav-cpu-saturation-esp-bridge-verified-correct
description: "Robot won't move under Nav2. Two root causes confirmed 2026-06-02 — Nav2 controller saturates the 4-core Pi, and the pivot PWM is too weak. The ESP/safety_gate bridge itself is CORRECT."
metadata: 
  node_type: memory
  type: project
  originSessionId: 0bcdbf73-85e5-4cbe-95d8-54967782d2e3
---

# Why a Nav2 goal sends but the robot won't move (verified 2026-06-02)

Goal pipeline is fully working (goal -> [[project_foxglove_viz]] goal_relay -> navigate_to_pose
action -> controller -> /cmd_vel_nav -> smoother -> collision_monitor -> /cmd_vel -> safety_gate).
The gate logged `TURN w=-0.11 mag=142 -> M,142,-116` continuously, yet rf2o yaw stayed FROZEN
(~0.3 deg over 6 s when ~38 deg expected). Robot physically did not pivot.

## ESP serial bridge / safety_gate is CORRECT (the user's "is the bridge right?" question — answer: YES)
Verified live on 2026-06-02:
- Running node = `install/medidroid_base/lib/medidroid_base/safety_gate` (PID held /dev/ttyESP32).
- `/dev/ttyESP32 -> ttyUSB0`, opened `serial.Serial('/dev/ttyESP32',115200,timeout=0.05)`, held by
  safety_gate (fuser confirms). Frames `f'M,{pwm_l},{pwm_r}\n'` via `self.ser.write(cmd.encode())`.
- LIVE constants: MAX_PWM=150, MIN_PWM=55 (deadzone bumps 0<|pwm|<55 up to 55), RIGHT_SCALE=0.82,
  TURN_PWM_MIN=140, TURN_PWM_MAX=150, TURN_W_REF=0.5, TURN_V_MAX=0.03, TURN_W_MIN=0.05.
- Pivot math for w=-0.11: frac=min(1,0.11/0.5)=0.22; mag=int(140+10*0.22)=142; w<0 -> `_send(142,-142)`;
  in `_send`, right side = int(-142*0.82) = -116 -> emits `M,142,-116`. EXACTLY matches observed log.
- NOTE the older [[project_nav_fix_plan]] said "robot cannot spin in place, arc turns only" — that is
  STALE. The live safety_gate now HAS a sustained in-place pivot block (closed by IMU yaw feedback).

So the bridge does exactly what it is designed to. It is NOT the fault.

## Root cause #1 — Nav2 controller saturates the 4-core Pi (the dominant problem)
During active navigation, load hit 9.8–11.5 on 4 cores; rf2o exec time 26–48 ms (should be ~5);
goals ABORTED; the Pi even stopped answering SSH/WiFi until the goal was Ctrl+C'd (the user's remote
control stayed up — it's a separate device; only the laptop->10.42.0.1 path died). The Foxglove
bridge was NOT the hog: whitelisting costmaps off it cut its subs to 0 but load stayed ~9.8.
Suspect the **controller plugin** (if MPPI, far too heavy for a Pi). NEXT: inspect the nav launch's
controller config and lighten it (cut iterations / switch to RegulatedPurePursuit / drop rates).
Saturation also causes **watchdog stutter**: a starved controller publishes /cmd_vel in bursts, and
safety_gate's 0.5 s watchdog injects `M,0,0` between bursts -> motors never get a sustained push ->
can't break static friction even if PWM were adequate.

## Root cause #2 — pivot PWM too weak for a 4-wheel in-place pivot
142/116 is at the very bottom of the breakaway band. Worse, RIGHT_SCALE=0.82 (a STRAIGHT-LINE
correction for the faster right motor) drags the right pair down to 116 on pivots — exactly the side
that must push equally hard to rotate. For an in-place pivot all 4 wheels scrub sideways (needs more
torque than driving straight). Candidate fixes (NOT yet applied — need floor cleared + user "go"):
  (a) do NOT apply RIGHT_SCALE during a pivot (pivots want symmetric magnitude);
  (b) floor pivots near MAX_PWM (raise TURN_PWM_MIN toward 150);
  (c) check ESP firmware whether PWM can exceed 150.
Cross-ref [[project_motor_dead.md]]: motors/driver/power are fine; direct serial moves the robot
with safety_gate STOPPED. And [[project_motion_primitives]] has a VALIDATED in-place turn — compare
its PWM/symmetry to see why the validated primitive turns but the Nav2 path doesn't.

## RESULT 2026-06-02: VERIFIED WORKING — robot drove a Nav2 goal and REACHED the destination
After both restarts the user sent a goal and the robot navigated to it and arrived (first end-to-end
Nav2 success on hardware). Confirmed live: amcl max_particles=1500, max_beams=60,
controller_frequency=5.0, local_costmap update=3.0; safety_gate restarted with PIVOT_KICK live;
nav2_container idle CPU dropped ~86% -> ~64% of a core. So: pivot breakaway kick + CPU cuts = the
robot moves under Nav2. NEW open issue (see [[project_localization_scan_swim]]): it reached the goal
by spiralling/circling first — the live /scan visibly drifts out of alignment with the map, then snaps
back, repeatedly, during motion (a localization/odom-yaw oscillation).

## FIXES DEPLOYED 2026-06-02 (both pending a restart + a "go" to verify with motion)
1. **Pivot breakaway kick** — safety_gate.py now opens every in-place pivot with a full-power KICK
   (`PIVOT_KICK_PWM=150` for `PIVOT_KICK_T=0.25 s`) then falls to the 140-150 proportional hold.
   `self._pivot_since` tracks the pivot start and resets on stop/drive/watchdog so a burst/stuttered
   command stream re-kicks each time. Mirrors the validated turn primitive (kick 150, hold ~110).
   Deployed to src + install site-packages; both py_compile OK. **Restart:** in the safety_gate
   terminal `Ctrl+C` then `ros2 run medidroid_base safety_gate` (it's a plain `ros2 run`, PID-owned,
   not in nav2_container).
2. **CPU cuts in nav2_params.yaml** — the hog was `nav2_container` (~86% of one core at IDLE, holds
   amcl+costmaps+controller+planner+bt). Lowered: AMCL max_particles 3000->1500, min 1000->500,
   max_beams 120->60, update_min_a/d 0.05->0.1; controller_frequency 10->5; local_costmap
   update 5->3 / publish 2->1; velocity_smoother smoothing 10->5. (docking controller_frequency 50
   left as-is.) safety_gate's own 360 LiDAR guard stays the real-time obstacle stop, so lower costmap
   rates are safe. Deployed to src config + install share; YAML parses. **Restart:** Ctrl+C the nav
   launch (T3) and re-run it (`ros2 launch medidroid_base nav_launch.py map:=/home/medidroid/mapp.yaml`).
   **UPDATE 2026-06-02 (anti-overshoot; user: "increase to max even if it takes CPU"):** reverted two cuts —
   controller_frequency 5->10 and update_min_a 0.1->0.05 (and smoothing_frequency 5->10 to match) — to give the
   loop speed to STOP an in-place turn before it overshoots. Big CPU savers STAY cut (particles 1500, beams 60,
   costmap 3/1), so responsiveness returns without recreating saturation. Paired with the pulsed pivot in
   [[project_localization_scan_swim]]. If an active goal saturates the Pi again, dial controller back to ~7-8.
Backups of all four files saved alongside as `*.bak_<ts>`. Other live CPU users (not yet touched):
foxglove_bridge ~22%, rf2o ~23%, imu_mpu9255 python node ~14.5% — candidates if load is still high.

**Why:** user asked "check the esp bridge, is it correct?" — it IS; the blockers were CPU saturation
(container) + no breakaway kick on the pivot. Both now fixed in code/config.
**How to apply:** After the two restarts, re-measure `top`/`uptime` under an active goal to confirm
load stays low and the robot actually pivots (watch rosout for `TURN[KICK]`). If still heavy, throttle
foxglove (/scan), the python imu node, or rf2o next. No motion until the user clears space + says "go".
