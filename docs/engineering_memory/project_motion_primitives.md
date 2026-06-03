---
name: motion-primitives
description: "VALIDATED MediDroid motion architecture — drive(m) via rf2o-yaw closed loop, turn(deg) via LiDAR xcorr. Constants, key sensor insights, script locations, and the room-101 hybrid next step."
metadata: 
  node_type: memory
  type: project
  originSessionId: 0396d2e6-e698-416c-a89f-2c9ddf9a6b96
---

# MediDroid Motion Primitives (validated 2026-05-31)

The user's standing architecture: **kill encoder reliance completely**; build `turn(degrees)` + `drive(meters)` primitives, compose them into routes, and eventually **read the Nav2-planned path (`/plan`) and convert it into measured turn+drive segments** (hybrid: real planning + measured execution, NOT hardcoded, NOT open-loop). Both primitives are now validated; the hybrid is the open next step.

## The key sensor insight (this is THE reason for the architecture)
**rf2o_laser_odometry is the only odometry.** Its yaw **tracks heading well DURING translation** (it has motion to scan-match against) but is **BLIND to in-place rotation** (converts spin to phantom translation — a 90° hand-rotate read as 14°). rf2o **distance is accurate** (1m=1m confirmed). Therefore:
- **drive(m) → closed loop on rf2o /odom yaw** (continuous proportional steering).
- **turn(deg) → LiDAR scan cross-correlation (xcorr)**, robot stopped before/after each pulse.
- **Never** do mid-drive xcorr heading correction: translation between scans contaminates xcorr → it over-reads drift → over-rotates. (This bug ended a run "way left" while the script reported +1.5°.)

## Motor imbalance (had this BACKWARDS earlier — now settled)
Robot **always veers LEFT at equal PWM because the RIGHT wheel is mechanically STRONGER**, so the right wheel must be **CUT**. drive bakes this into `R0=82` (vs `L0=100`); turns apply `RIGHT_SCALE=0.80` inside the pulse. (safety_gate's `RIGHT_SCALE=0.80` is correct for the same reason.) Do NOT boost the right wheel.

LiDAR is mounted BACKWARD: base_link→laser `x=0.1, yaw=π`. Front-arc detection for the backward mount: `(math.pi-abs(angle)) <= FRONT_ARC`. User note: the LiDAR's measured rotation reads slightly LOW vs the body ("shift of the lidar is lower than the robot itself").

## Validated constants
- **drive** (drive_yaw.py): `L0=100, R0=82, KP=2.5` PWM/deg, `TRIM_MAX=±35`. send() uses **NO RIGHT_SCALE** (R0=82 already balances). Stop on `hypot(dx,dy) >= DIST`. Result: 1m straight, yaw held ±0.9°, trim stayed ±2. User: "beautiful clear straight."
- **turn** (xcorr): `TOL=6°, MAXIT=16`, settle 0.45s after each pulse, taper `run = 0.45 if rem>35 else (0.22 if rem>15 else 0.12)`, `sgn=+1` for LEFT/CCW. pulse = 0.13s kick at ±150 then ±110 for `run` s, then stop.
- **shared:** `MIN_PWM=55` (stall floor), `MAX_PWM=150`, `FRONT_STOP=0.30m`, `FRONT_ARC=1.047` rad (±60°). ESP32 `/dev/ttyESP32` @115200, protocol `M,leftPWM,rightPWM\n`.
- Known minor: after a turn, the next drive sees a brief yaw transient (~+7.6°) from turn coast / rf2o resettle; the drive controller absorbs it. A longer post-turn settle would smooth it.

## Scripts (local, EPHEMERAL — Windows Temp, not a repo)
- `C:\Users\abadi\AppData\Local\Temp\drive_yaw.py` — validated straight drive (THE drive primitive).
- `C:\Users\abadi\AppData\Local\Temp\exec_seq.py` — validated combined executor; runs comma-seq like `D0.5,T90,D0.5` (D=drive, T=turn deg, +=LEFT). Validated tracing a clean "L". User: "beautifull. it did what it should do."
- Pattern: SFTP a rclpy node to `/tmp`, run `bash -lc 'ENV python3 /tmp/x.py args 2>&1'`. Hard-stop motors in a `finally` block (firmware watchdog is DISABLED — last command latches = runaway).

## Operational gotchas
- **Port exclusivity:** only one process owns `/dev/ttyESP32`. **safety_gate (T2) must be Ctrl+C'd** before running any direct-serial primitive (scripts self-guard with `fuser` → "PORT BUSY"). With T2 stopped, direct-serial works perfectly — this corrects the old "direct-serial = silent motors" note, which was the gate watchdog interleaving `M,0,0`. See [[project-motor-dead]].
- ESP32 only enumerates when the motor power rail is ON (USB VBUS/red wire is cut). After a battery swap it may vanish until power is restored.

**Why:** captures the hard-won, NON-obvious sensor/motor facts and the exact validated constants so future sessions don't re-derive them (the scripts are in Temp and will be wiped).
**How to apply:** when extending motion or building the room-101 route / Nav2-`/plan`→segments hybrid, reuse these primitives & constants; respect the rf2o yaw-vs-xcorr split and the right-wheel-cut. Honor [[feedback-robot-ops]] (deploy + clear-space-then-"go"). Related: [[project-medidroid]], [[project-nav-fix-plan]].
