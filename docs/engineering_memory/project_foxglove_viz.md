---
name: foxglove-viz-rviz-replacement
description: Foxglove Studio on laptop replaces CPU-heavy software-RViz on the Pi. foxglove_bridge + goal_relay deployed; topic whitelist excludes costmaps.
metadata: 
  node_type: memory
  type: project
  originSessionId: 0bcdbf73-85e5-4cbe-95d8-54967782d2e3
---

# Foxglove Studio replaces RViz-on-the-Pi (2026-06-02)

The user needs to SEE the map and click Pose-Estimate / Goal visually ("idk the location by
numbers, i need rviz2"). Running RViz/heavy viz ON the Pi is a CPU hog. Solution: **Foxglove
Studio 2.53.1 (desktop, Windows laptop) talks to foxglove_bridge (ROS2 node on the Pi, WebSocket
:8765)** over the Medidroid AP. Pi only serializes topics; the laptop GPU renders.

## Deployed pieces
- **`/home/medidroid/viz_launch.py`** — the "T4 terminal". Launches `foxglove_bridge` (Node) +
  `goal_relay.py`. Run: `ros2 launch /home/medidroid/viz_launch.py`. Bridge params:
  port 8765, address 0.0.0.0, `topic_whitelist` (light topics only), use_compression=False
  (CPU is the bottleneck, not bandwidth), max_qos_depth=5.
  WHITELIST = /map /scan /tf /tf_static /goal_pose /move_base_simple/goal /initialpose
  /clicked_point /plan /amcl_pose /odometry/filtered /robot_description /rosout.
  **Costmaps (/global_costmap/*, /local_costmap/* + _updates) are EXCLUDED** — they were the heavy
  WebSocket streams. Whitelist CONFIRMED working (0 foxglove_bridge subs on /local_costmap/costmap).
- **`/home/medidroid/goal_relay.py`** — Nav2 core has NO `/goal_pose` subscriber (RViz's Nav2 panel
  secretly calls the `navigate_to_pose` action; Foxglove has no such plugin). This relay subscribes
  to BOTH `/goal_pose` AND `/move_base_simple/goal` (Foxglove "Publish Pose" defaults to the latter)
  and forwards to the `navigate_to_pose` action. Run via `python3 -u` (no colcon build, matches imu
  node pattern). VERIFIED: forwarded a goal end-to-end (x=0.638 y=1.962). Logs "Relaying goal", "Goal
  accepted; navigating...", "distance_remaining=.. m", "Goal finished: SUCCEEDED/ABORTED".
- **`C:\Users\abadi\Desktop\medidroid_foxglove_layout.json`** — importable layout: single 3D panel,
  followTf:map, follow-none, perspective:false (top-down 2D), /map+/scan+/plan visible, costmaps
  hidden, publish.poseTopic=/goal_pose, poseEstimateTopic=/initialpose.

## Foxglove gotchas the user hit
- Map "looks weird" = it was tilted in 3D perspective + user was on the example-001-av demo layout.
  Fix: Display frame=map, toggle 3D->2D, import the clean layout.
- Layout "type doesn't match" on import = user used the Open-data-source dialog (accepts only
  .mcap/.bag/.foxe). Fix: **Layouts sidebar -> Import from file**, set picker to All Files.

## Source files (Windows, push via paramiko/SFTP)
viz_launch.py and goal_relay.py live in `C:\Users\abadi\AppData\Local\Temp\`. redeploy_viz.py /
redeploy_relay.py SFTP + py_compile them. Install via deploy_foxglove.py (`apt-get install -y
ros-jazzy-foxglove-bridge`).

**Why:** user wanted visual goal-setting without paying the Pi-side RViz CPU cost.
**How to apply:** to show the map / set goals, have the user run `ros2 launch
/home/medidroid/viz_launch.py` on the Pi and connect Foxglove to ws://10.42.0.1:8765. See
[[project_nav_cpu_and_esp]] for why even the whitelisted bridge didn't fix the load problem.
