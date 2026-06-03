---
name: localization-scan-swim-circling
description: "Robot reaches Nav2 goals but circled/hunted L-R + 'turned then cancelled'. RESOLVED 2026-06-03 (user: 'best version so far'): the L/R rock and turn-then-cancel were the SAFETY_GATE's OWN pulse/reversal state machine fighting Nav2 — NOT a localization fight. Fix = (1) gate rewritten to a FAITHFUL PASSTHROUGH (no pulse/no reversal-lock/no watchdog-stop; continuous 140-150 PWM floored by |w|, sign from Nav2, stop when |w|<0.06); (2) AMCL heading=IMU via alpha1/alpha2=0.02 (verified steady); (3) CPU cuts stop goal-aborts that triggered fixed-direction Spin recovery. See LATEST section for the validated config + the Nav2 BT spin/backup gotcha."
metadata: 
  node_type: memory
  type: project
  originSessionId: bc99ed16-a920-401a-a455-38fca7e4f22a
---

# Robot reaches the goal but CIRCLES first; live /scan swims off the map (2026-06-02)

Once [[project_nav_cpu_and_esp]] fixes landed and Nav2 drove a real goal, a new symptom is clear:
the robot does NOT take a clean path — it loops/spirals around itself, then converges on the goal.

## The user's own theory (watching Foxglove during the run) — almost certainly correct
The live `/scan` (red points) periodically goes **OUT OF ALIGNMENT** with the map walls, then
**snaps back into place**, then drifts out again — oscillating the whole time the robot moves. The
user reads this as "that is why it gets lost." Each time the scan/pose belief jumps, the controller
re-plans against a moved pose -> the robot turns to chase it -> circling.

## Leading root cause (to verify): odom->base_link YAW doesn't track real rotation
This robot's documented hard fact ([[project_motion_primitives]]): **rf2o_laser_odometry yaw is BLIND
to in-place rotation** (a 90deg spin reads ~14deg). rf2o is the odom source. The EKF (ekf.yaml) is
supposed to fix yaw by fusing the MPU9255 IMU gyro. If the EKF is still fusing rf2o's (wrong) yaw, or
not trusting the IMU yaw-rate enough, then during every turn odom yaw lags reality -> the scan,
transformed map->odom->base_link->laser, renders rotated wrong (swims) -> AMCL fights to correct
map->odom -> snap back -> repeat. This matches the circling EXACTLY.

## Fix direction (NEXT SESSION — needs charged battery + read-only first)
1. Read `/home/medidroid/ekf.yaml`: check odom0(rf2o) and imu0(mpu9255) config matrices.
   - rf2o (odom0) should fuse **vx, vy only** (translation) — NOT yaw, NOT vyaw.
   - IMU (imu0) should fuse **yaw + vyaw** (rotation) — and `imu0_differential`/`_relative` sane.
   This "translation-from-laser, rotation-from-IMU" split is the correct config for rf2o's blindness.
2. Verify the MPU9255 yaw is actually good: compare IMU yaw vs commanded turn over a known rotation.
   imu_mpu9255_node.py is a Python node (~14.5% CPU) — confirm it outputs orientation+angular_vel.
3. Check TF latency/`transform_tolerance` (amcl=1.0) now that CPU is lighter — stale TF also makes
   scan swim; the (now-fixed) saturation was likely worsening it.
4. Consider AMCL trust: with odom yaw fixed, lower update churn; current update_min_a/d=0.1.

**Why:** first Nav2 success exposed a localization-quality problem, not a motion problem. The circling
wastes path and risks "getting lost" on a larger map. User is invested in fixing it.
**How to apply:** start read-only (ekf.yaml + IMU yaw sanity + TF rates); the most likely single fix is
making the EKF take yaw ONLY from the IMU and translation ONLY from rf2o. No motion until floor cleared
+ "go". Battery was LOW when found — defer live tests. Related: [[project_nav_fix_plan]] (had flagged
initial-localization as the suspect), [[project_motion_primitives]] (rf2o yaw-blindness fact).

## 2026-06-02 REFINED diagnosis + PULSED-PIVOT fix deployed (user's over-rotation theory)
Read-only follow-up CLEARED two of the original suspects and pivoted to a new one:
- **EKF config is CORRECT** (verified): odom0=/odom rf2o fuses X,Y position only (yaw excluded);
  imu0=/imu/data_raw fuses VYAW (gyro yaw-rate) only. Proper laser-translation / IMU-rotation split.
- **IMU deadband is NOT the culprit** (cleared): imu_mpu9255_node.py uses DEADBAND=0.6 deg/s and
  STILL_THRESH=0.8 deg/s — ~10x below even a slow 0.1 rad/s (5.7 deg/s) Nav2 turn, and bias-tracking
  freezes during real rotation. So slow turns are NOT being eaten by the deadband. Do NOT touch the IMU
  deadband (it suppresses a real ~3 deg/min yaw creep).
- **User's own NEW theory (correct & actionable):** the robot OVER-rotates into an endless turn loop
  ("turns so much it enters an infinite loop"); recommended small PULSED turning like the validated
  primitive. Mechanism confirmed in code: **safety_gate floors EVERY in-place pivot into the 140-150 PWM
  band — the magnitude of commanded angular.z does NOT slow the physical spin** (frac=|w|/0.5 saturates
  for any |w|>=0.25). So Nav2's `rotate_to_heading_angular_vel` cannot slow the pivot; the ONLY place to
  slow it is safety_gate. A steady full-PWM pivot + the (just-lowered-for-CPU) 5Hz controller + coarse
  AMCL (update_min_a 0.1) = the loop can't stop the turn before it overshoots -> heading error flips ->
  rotates back -> circles. The earlier CPU cuts likely WORSENED this overshoot.
- **FIX DEPLOYED (safety_gate.py, src+install, py_compile OK, backups *.bak_20260602_174420):** replaced
  the sustained pivot with a PULSED pivot. New constants: PIVOT_KICK_PWM=150, PIVOT_KICK_T=0.20 (initial
  continuous breakaway kick), then PIVOT_PULSE_ON=0.12 / PIVOT_PULSE_OFF=0.18 (drive/coast). Driven by a
  new 20Hz `self.pivot_timer`->`_pivot_tick` (the 5Hz /cmd_vel can't pulse on its own — the ESP latches
  the last frame). `_on_cmd` now just RECORDS the turn (`_pivot_w`,`_pivot_since`,`_pivot_cmd_time`); a
  0.3s pivot-watchdog in `_pivot_tick` ends the turn when Nav2 stops asking. nav2_params NOT changed this
  round (commanded w can't slow the floored pivot, so it would only muddy the test). Constants are the
  tuning knobs: turns too slow/stalls -> raise ON or lower OFF; still overshoots -> lower ON or raise OFF.
- **RESTART to apply:** only safety_gate needs it (nav stack unchanged): in its terminal Ctrl+C then
  re-run `ros2 run medidroid_base safety_gate`. Watch rosout for `TURN[KICK]` / `TURN[pulse-ON]` /
  `TURN[pulse-OFF]`.
- **REMAINING odom-yaw suspect = gyro SCALE.** If after pulsing the /scan STILL swims on a clean slow
  turn, the EKF yaw is tracking the wrong RATE (gyro FSR/scale in the MPU9255 driver, not shown in
  node lines 130-236). Verifying needs a CONTROLLED known rotation (motion) -> next session w/ "go".
  Pulsing fixes the CONTROLLER-side overshoot; gyro-scale (if wrong) is the PERCEPTION-side swim.

## 2026-06-02 LIVE CAPTURE (pulse + 10Hz loop deployed) — robot STILL hunts L/R. Root found.
User: "watch live of how it tries and goes over left and over right even with pulses.. why?" Ran a
read-only 25s time-aligned capture (yaw_watch driver -> /tmp/yaw_watch.py: /cmd_vel cmdW, /cmd_vel_nav
navW, /imu/data_raw gyroZ dps, /odometry/filtered ekfYaw, /odom rf2oYaw, /amcl_pose amclYaw @10Hz).
Findings (this is the authoritative diagnosis — supersedes the gyro-scale guess above):
- **Pulse WORKS** — cmdW tracks navW; gyroZ shows clean pulsed spikes. Actuator side is fixed.
- **Oscillation ORIGINATES at the controller (navW), not safety_gate.** navW flips sign violently the
  whole run (+0.49 -> -0.64 -> +0.52 -> -0.26 -> +0.59 ...). Nav2 keeps reversing its TARGET direction.
- **Why the controller hunts: it servoes AMCL map heading, which is SLOW + JUMPY.** Msg counts/25s:
  imu 2521 (~100Hz), ekf 790 (~31Hz), cmd/nav ~250 (~10Hz), **amcl 53 (~2Hz)**. amclYaw jumps ±15-20°
  per update (e.g. 5.2->18.0->1.3->-10.1 in 4 updates). A 10Hz controller chasing a 2Hz reference that
  jumps ±20° = limit-cycle hunt. velocity_smoother adds ~0.25s phase lag (cmdW trails navW).
- **GYRO SOFTWARE SCALE = RULED OUT (was the leading suspect — now cleared).** /home/medidroid/
  imu_mpu9255_node.py L79 writes REG_GYRO_CONFIG=0x08 (GYRO_FS_SEL=01 = ±500 dps); L83 gyro_scale=1/65.5.
  65.5 LSB/(deg/s) is the exact datasheet sensitivity for ±500 dps. Conversion is CORRECT. (EKF-vs-AMCL
  delta gap is real but confounded — AMCL delta isn't pure rotation + 2Hz quantized — NOT a code bug.)
  NOTE: IMU node is a STANDALONE script at /home/medidroid/imu_mpu9255_node.py (PID-run via ExecuteProcess
  in nav_hardware_launch.py / imu_hardware_launch.py), NOT in ros2_ws. WHO_AM_I gate accepts 0x71/0x73.
- **THE SMOKING GUN (proven live): the actuator has NO proportional softness.** Even tiny navW produces a
  FULL pivot burst: navW=0.10 -> gyroZ≈20.9 dps; navW=0.15 -> 20.0; navW=0.25 -> ~same. safety_gate's
  TURN_W_MIN=0.05 floor makes ANY |w|>0.05 a full-authority pulsed pivot. So every heading error (however
  small) slams a full pivot -> overshoot -> AMCL jumps back -> full pivot the other way = the L/R rocking.
- **FIX DEPLOYED 2026-06-02 (user said "FIX IT ALL"; src+install, py_compile OK, YAML OK, backups
  *.bak_20260602_182035).** Two changes attacking the two proven mechanisms:
  1. **safety_gate.py — proportional/duty-scaled PULSE + deadband + re-kick cooldown** (gives the floored
     pivot the proportional softness it lacked). New/changed constants: TURN_W_MIN 0.05->**0.12** (DEADBAND:
     when ~stationary, |w|<0.12 -> M,0,0 hold-still, drops micro-corrections that were slamming full pivots);
     TURN_W_REF=0.5 repurposed as the duty reference; PIVOT_PULSE_ON_MIN=0.06/ON_MAX=0.16,
     OFF_MIN=0.12/OFF_MAX=0.24 (duty scales with |w|: small w -> short ON/long OFF = gentle; large w ->
     long ON/short OFF = fast); PIVOT_KICK_PWM=150/KICK_T=0.20 unchanged; PIVOT_KICK_COOLDOWN=0.40 (new
     self._pivot_last_active gates the breakaway kick so a deadband dip between reversals doesn't re-kick).
     _pivot_tick computes frac=min(1,|w|/TURN_W_REF) -> on/off each tick. _on_cmd: deadband branch
     (|v|<TURN_V_MAX & |w|<TURN_W_MIN -> stop) then pivot branch (|w|>=TURN_W_MIN -> record + arm w/ cooldown).
  2. **nav2_params.yaml — AMCL max_beams 60->100** (sharper scan likelihood -> heading reference stops
     jumping ±20°). ~150k beam-evals/update, well under the ~360k that saturated the Pi. Particles STAY
     cut at 1500; update_min_a stays 0.05; controller 10Hz; docking 50.0 untouched.
  **RESTART:** T2 safety_gate (Ctrl+C, `ros2 run medidroid_base safety_gate`) AND T3 nav (Ctrl+C,
  `ros2 launch medidroid_base nav_launch.py map:=/home/medidroid/mapp.yaml`) — nav2_params loads at launch.
  May need to re-set 2D Pose Estimate after. WATCH rosout: TURN[KICK] once then short/long pulse-ON by |w|;
  tiny corrections -> NO pivot. **CPU valve:** if goals ABORT (saturated by beams), restore nav2_params
  install copy from .bak_20260602_182035 + restart T3; safety_gate fix is independent and stays.
  **Tuning knobs** if still off: turns too slow/stall -> raise ON_MAX or lower OFF_MAX; still overshoots ->
  lower ON_MAX or raise OFF; deadband drops real turns / too twitchy -> adjust TURN_W_MIN. Counterpoint to
  "max responsive": a 10Hz controller on a 2Hz jumpy reference AMPLIFIES hunt — if 100 beams isn't enough,
  next lever is lowering controller_frequency to low-pass the AMCL jumps (trades against user's max pref).
  **AWAITING the user's cleared-floor "go" + live test to confirm the hunt is gone.**

## 2026-06-02 STILL rocking 3 min (proportional pulse + 100 beams didn't fix it). DEFINITIVE 75s capture.
User: "its been 3 minute, same place going right and left. its obvious that two logics are fighting...
if not fighting logic then it must be lidar, let's do delay of lidar after a pulse and reached angle
needed to 1s, angles less than 25 degrees needed ignored." Ran read-only 75s THROTTLED capture
(capture_nav_long.py: /cmd_vel_nav, /cmd_vel, /rosout TURN/Rotat; prints only on sign-flip / >0.02 az
change / lx>0.02). This is the AUTHORITATIVE shape of the rock — supersedes guesswork above:
- **/cmd_vel_nav linear.x = 0.000 for the ENTIRE 75s.** The robot NEVER tries to drive — it is stuck in
  pure in-place rotation the whole time. So this is NOT a path/drive problem; it's a rotate-to-heading
  that never converges.
- **angular.z sign-flips ~5x/sec, range -0.66..+0.60.** The controller reverses its TURN TARGET every
  ~10Hz cycle. The smoother makes a ±0.1-0.2 sawtooth, ramping toward its 0.6 clamp when the controller
  briefly commits. The gate faithfully fires a 150-PWM kick at every zero-crossing = the violent rock.
- **CONCLUSION: the gate is downstream of and faithful to a controller that is itself oscillating.** My
  earlier rotate_to_heading=1.0 theory was DISPROVEN by probe_navstate.py (controller commands SMALL w
  ~0.10, lx=0). The root limit-cycle is controller-chases-2Hz-jumpy-AMCL (same mechanism as above).
- **FIX DEPLOYED (user's intent; safety_gate.py src+install, py_compile SRC_OK/INST_OK, 6 markers each,
  backups *.bak_20260602_185256):** (1) TURN_W_MIN 0.12->**0.30** — raises the deadband so the smoother's
  ±0.1-0.2 noise band no longer triggers a pivot; only a committed turn (the 0.6 ramps) gets through.
  Safe because yaw_goal_tolerance=1.0 rad and it only applies in-place (|v|<TURN_V_MAX). (2) new
  **PIVOT_SETTLE_HOLD=1.0** s + self._pivot_hold_until state: when a pivot ENDS (deadband branch OR the
  0.3s pivot-watchdog in _pivot_tick), arm a 1s window during which NEW pivots are suppressed (M,0,0) so
  the controller+AMCL converge before any reversal. KEY: a SUSTAINED same-direction turn keeps
  |w|>=0.30 so it never "ends" and is NOT chopped — only oscillating reversals get the hold.
  This implements the user's "delay 1s after a pulse" + "ignore small angles" (as an angular-VELOCITY
  deadband 0.30 rad/s, since the gate sees w not heading-degrees — a true <25deg heading deadband would
  live in the controller, which RPP doesn't expose). nav2_params NOT changed this round.
- **RESTART:** only safety_gate (nav unchanged): T2 Ctrl+C then `ros2 run medidroid_base safety_gate`.
- **TWO OUTCOMES to watch (this is the decision branch):** (1) WIN — far fewer TURN[KICK] lines, a
  committed turn shows KICK->pulse then ~1s silence, then linear.x>0 = it drives. (2) STUCK STILL — it
  sits and never makes a committed correct turn = the gate filtered the noise but the controller still
  can't pick a direction; root is AMCL heading jitter / rf2o rotation-blindness and the NEXT lever is
  **controller-side** (`use_rotate_to_heading: false`, or lower `rotate_to_heading_angular_vel`, or lower
  controller_frequency to low-pass AMCL) or localization quality. The gate can FILTER noise but cannot
  CREATE a good command. **AWAITING user's live-test report to pick the branch.**

## 2026-06-03 ✅ BEST VERSION SO FAR (user: "SAVE EVERYTHING... best version we have done so far. GOOD JOB")
The whole 2026-06-02 pulse/duty/deadband/reversal-dwell saga ABOVE is now SUPERSEDED. The decisive
realization: the "turn then cancel" and "kept turning left then froze" the user kept seeing was the
**safety_gate's own pivot state machine**, not Nav2 and not localization. The gate was a SECOND control
logic fighting the first. Resolution = strip the gate to a dumb translator and let Nav2 (closed on the
IMU) own all steering. Validated direction; user very happy.

### Heading = IMU (the part that WAS right and stays)
- AMCL `alpha1: 0.02`, `alpha2: 0.02` (alpha3/4/5 stay 0.2). Locks the particle-cloud yaw spread to ~0 so
  AMCL stops re-deriving heading from the 2Hz LiDAR scan-match and follows the IMU-integrated odom yaw;
  LiDAR still corrects X/Y. VERIFIED LIVE: map->odom offset held steady ~164° (no more ±20° jumps).
- Chain: MPU9255 gyro -> EKF -> odom->base yaw (REAL heading; rf2o is yaw-blind) ; AMCL -> map->odom (X/Y).
  Nav2 RPP compares (map->base heading) to goal -> sets w. IMU=direction/when-to-turn, LiDAR=where-on-map.

### safety_gate.py = FAITHFUL PASSTHROUGH (the big change; replaces ALL pulse/reversal machinery)
DELETED: pivot_timer/_pivot_tick, KICK, ON/OFF pulses, PIVOT_SETTLE_HOLD reversal-dwell, _pivot_last_dir,
the 0.3s pivot-watchdog stop, and all _pivot_* state. WHY: every pivot used to be drive->M,0,0->drive->
M,0,0 (the "cancel"), and the reversal-dwell LOCKED direction (blocked the opposite turn for 0.5s -> "kept
turning left, won't undo"). That machine WAS the symptom. New `_on_cmd` in-place-pivot branch (the ONLY
turn code): if |v|<TURN_V_MAX: if |w|<TURN_W_MIN -> M,0,0 hold; else frac=min(1,(|w|-TURN_W_MIN)/
(TURN_W_REF-TURN_W_MIN)); turn_pwm=int(140+(150-140)*frac); w>0 -> _send(-turn_pwm,+turn_pwm) (LEFT/CCW),
w<0 -> _send(+turn_pwm,-turn_pwm) (RIGHT/CW); continuous every frame, stops the instant Nav2 drops |w|.
Constants now: TURN_V_MAX=0.03, **TURN_W_MIN=0.06**, TURN_PWM_MIN=140, TURN_PWM_MAX=150, TURN_W_REF=0.5.
Turn sign is hardware-verified (w>0=left; the earlier w-negation was removed after a right_test). Gate still
keeps: LiDAR 360° safety stops, 0.5s no-cmd watchdog, RIGHT_SCALE=0.82, _send deadzone/clamp, drain thread.
Logs `TURN w=±0.NN pwm=NNN -> M,l,r` per frame (sign = Nav2's commanded direction).

### nav2_params.yaml CPU cuts (stop goal-aborts -> stop fixed-direction Spin recovery)
max_beams 60, **max_particles 500, min_particles 200** (yaw rigid -> tight X/Y cluster needs few),
`always_send_full_costmap: False` on BOTH costmaps (send incremental costmap_updates, not full grid each
cycle — biggest serialize saving), local costmap `raytrace_max_range: 2.0`/`obstacle_max_range: 1.8` (3x3m
grid = 1.5m half-width, longer ranges compute cells outside it), RPP `lookahead_dist: 0.6`/`min 0.4`
(low-pass path steering). Unchanged: controller 10Hz, yaw_goal_tolerance 1.0, xy 0.5, rotate_to_heading
min_angle 0.785 / vel 1.0, velocity_smoother max [0.18,0,1.2].

### ⚠️ NAV2 BT GOTCHA (cost a cycle — do NOT repeat): can't remove spin/backup via behavior_plugins
Deleting "spin"/"backup" from `behavior_server: behavior_plugins` BREAKS the whole stack: the default BT
`navigate_to_pose_w_replanning_and_recovery.xml` hard-references <Spin>/<BackUp>, and **bt_navigator
validates EVERY referenced action server at tree-LOAD time (on_activate)** — a missing /spin server makes
the XML fail to load -> bt_navigator can't activate -> lifecycle_manager ABORTS bringup -> navigate_to_pose
server stays INACTIVE -> goals come back **"action server inactive, GOAL REJECTED"**. (REJECTED = lifecycle,
not tuning; ABORTED = accepted-then-failed = a different thing.) spin/backup are RESTORED in behavior_plugins.
To actually disable Spin: deploy a CUSTOM BT XML with the Spin/BackUp nodes stripped + set
`default_nav_to_pose_bt_xml` to it — NOT by deleting the plugin. Not yet needed: the CPU cuts keep goals from
aborting, so Spin stays dormant (it only fires on an abort). Do the custom-BT only if a wrong-way Spin recurs.

### Considerations CHALLENGED (a 2nd-AI suggested these; verdicts vs OUR config)
- Raise yaw_goal_tolerance to 0.15: MOOT — ours is already 1.0 rad (57°), 7x larger; the undershoot-abort
  trap can't happen at the goal. - Widen gate deadband to 0.10-0.12: REJECTED — re-creates the freeze we
  fought (zeroes RPP's gentle final turns); kept at 0.06. - Lower max_angular_accel: INERT — gate floors
  pivot PWM regardless of w magnitude. - Raise lookahead: APPLIED (0.5->0.6), the one genuinely useful one.

### Deploy + restart (current truth)
Deploy scripts (Windows Temp): `deploy_gate2.py` (gate src+install; trust py_compile SRC_OK/INST_OK, its
verify-grep is stale), `deploy_nav2_cpu.py` (nav2_params -> all 3 copies src/build/install + verify grep).
Restart: T2 gate `ros2 run medidroid_base safety_gate`; T3 nav `ros2 launch medidroid_base nav_launch.py
map:=/home/medidroid/mapp.yaml` (params load at launch — MUST relaunch to apply). Confirm `ros2 lifecycle
get /bt_navigator` = active[3] before sending a goal (probe_lifecycle.py). Goals 2+ m out.
### ONLY remaining unknown (check live if robot turns while VISIBLY aligned)
If, when the robot physically faces the goal, the gate still prints `TURN w=+...`, it's NOT the gate or
recovery anymore — it's IMU heading SIGN or the initial_pose yaw (-1.60) being offset from reality. Capture
AMCL-yaw-vs-actual on the first goal to confirm. Everything else is validated.