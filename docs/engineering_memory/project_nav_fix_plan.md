---
name: Nav2 Navigation Fix Plan
description: Nav2 "got lost" investigation for MediDroid. Static-TF theory DISPROVEN 2026-05-29 (live launch file was already pi). Leading suspect now initial localization.
type: project
originSessionId: 8208517f-8774-400b-9ce4-3e84edb25fc6
---
# Nav2 "Got Lost" Investigation

## CRITICAL CORRECTION (2026-05-29) — static-TF theory disproven for the live workflow
The earlier theory (this file's old version + a prior session) blamed a wrong base_link->laser
static transform. That is **not** the cause for how the user actually launches Nav2.

- The user launches by **full path**: `ros2 launch /home/medidroid/ros2_ws/src/nav_hardware_launch.py`.
  `ros2 launch <full-path>` reads THAT file directly — NOT the package share copy.
- That stray full-path file was **already `yaw=3.14159` (pi), `x=0.1`** before this session touched it
  (mtime 2026-05-17 16:04). Captured verbatim before overwriting — diagnostic gold.
- The `-30deg (-0.5236)` AND `x=-0.1` error existed **only in the package copy**
  (`.../medidroid_base/launch/...`, mtime 2026-05-16), which the full-path launch never loads.
- Conclusion: **the static transform was never wrong in the live runs**, so it cannot explain
  "got lost / spun / wandered." Do NOT re-chase the TF angle.

**Correct/established value: `arguments=['0.1','0','0.2','3.14159','0','0','base_link','laser']`.**
The old "yaw = 2.618 (150deg, pi - 30deg)" hypothesis was wrong — pi is correct (laser angle 0 = robot
REAR, no extra 30deg), proven by safety_gate's perfect obstacle avoidance which hardcodes that mount.

## Current file states on the Pi (verified 2026-05-29) — all consistent now
- Stray full-path file `/home/medidroid/ros2_ws/src/nav_hardware_launch.py`: **pi** (was already pi).
- Package src `.../medidroid_base/launch/nav_hardware_launch.py`: **pi** (fixed this session).
- Package install share: **pi** (rebuilt this session).
- So every launch path now loads the correct pi transform — no path loads a wrong one.
- `deploy_all.py` now pushes the launch file to BOTH the package path and the stray full-path file,
  so they can't diverge again.

## Leading suspect now: initial localization (NOT the TF)
- No saved AMCL pose exists on the Pi (deploy found `NO_POSE_FILE`). pose_manager warns to set the
  RViz **2D Pose Estimate** when there is no saved pose.
- If the initial pose (position AND heading) isn't set accurately before sending a goal, AMCL starts
  with a wrong belief, live scans don't match the map, and the robot spins/wanders trying to
  reconcile — exactly the reported symptom, and fully independent of the (correct) static TF.
- Next test MUST: set 2D Pose Estimate carefully, confirm `/scan` overlays the map walls and the AMCL
  particle cloud converges, THEN send a goal. Watch live: TF tree (map->odom->base_link->laser all
  present), `/scan` rate, `/amcl_pose`, `/cmd_vel`.

## Durable hardware facts (still valid)
- rf2o laser odometry is the odom->base_link source and was confirmed accurate. Encoders too noisy
  (+-10 on 30 ticks/rev) — unusable. Keeping rf2o (lidar-for-obstacles alone gives NO odometry).
- Weak motors: need high PWM to move. Right motor stronger -> RIGHT_SCALE=0.80 in safety_gate.
- Robot **cannot spin in place** — arc/car-style turns only. nav2_params has use_rotate_to_heading=false.
- safety_gate is the cmd_vel->ESP32 bridge (`M,pwm,pwm\n`) for BOTH scripted and Nav2 modes:
  WHEEL_BASE=0.34, MAX_VEL=0.20 (measured-low; true ~0.45), MAX_PWM=150, MIN_PWM=55; `w = msg.angular.z`.
- Scripted navigation (go_to.py, route_executor) is the proven-good "golden" path; calibrated turns
  (90deg) and distance (99cm) confirmed by user. Don't regress it when tuning Nav2.

## Deferred (only if OVERSHOOT appears after localization is sorted) — velocity model
- safety_gate MAX_VEL=0.20 undercounts true speed (~0.45). Raising it weakens angular authority
  (~2.25x) because `_vel_to_pwm` applies to combined wheel velocities. Plan: make max_vel a ROS param
  (default 0.20 keeps scripted golden), launch Nav2's safety_gate with `-p max_vel:=0.45`, and bump
  nav2_params desired_linear_vel + velocity_smoother to match. Do NOT do this for a "got lost" symptom.

**Why:** "Got lost" is a localization symptom, and the TF (the prior prime suspect) is now proven correct
in the live workflow. Chasing the TF further wastes time.
**How to apply:** Treat the static TF as solved. Investigate initial-pose / AMCL convergence first.
NEVER advise remapping — the map is consistent with the pi transform that actually ran.
