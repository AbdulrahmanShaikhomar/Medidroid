# Memory Index

- [MediDroid Robot Project](project_medidroid.md) — Full Pi state: SSH creds, USB ports, WiFi-dongle internet (RTL8821AU/rtl8812au), maps, ROS2 workspace, udev, launch files
- [Nav2 Fix Plan](project_nav_fix_plan.md) — Static-TF theory DISPROVEN (live file was already pi). Suspect now: initial localization. Do NOT remap.
- [Motors NOT Dead](project_motor_dead.md) — DISPROVEN: motors/driver/power fine. Direct-serial works with safety_gate stopped (gate watchdog was the cause of "silent motors").
- [Motion Primitives](project_motion_primitives.md) — VALIDATED drive(rf2o-yaw) + turn(LiDAR-xcorr), constants, right-wheel-cut, script paths, room-101 hybrid next step.
- [Robot Ops Rules](feedback_robot_ops.md) — Always deploy final nodes to Pi src+install & restart; never move the robot until user clears space and says "go".
- [Foxglove Viz](project_foxglove_viz.md) — Foxglove Studio on laptop replaces Pi RViz. viz_launch.py (bridge+whitelist) + goal_relay.py deployed; how to connect & set goals.
- [Nav CPU + ESP verified](project_nav_cpu_and_esp.md) — FIXED 2026-06-02: pivot breakaway kick + Nav2 CPU cuts → robot drove a goal & REACHED it. ESP bridge was always correct.
- [Localization scan-swim → SOLVED](project_localization_scan_swim.md) — ✅2026-06-03 BEST VERSION: L/R rock + turn-then-cancel was the safety_gate's OWN pulse/reversal logic. Gate now a faithful passthrough; heading=IMU (alpha1/2=0.02); CPU cuts. Nav2 BT spin/backup gotcha noted.
