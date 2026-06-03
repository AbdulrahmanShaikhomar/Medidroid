---
name: feedback-robot-ops
description: "How to operate on the MediDroid robot: always deploy final nodes to Pi src+install and restart; never command physical motion until the user clears space and says 'go'."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0396d2e6-e698-416c-a89f-2c9ddf9a6b96
---

# Operating rules for MediDroid physical work

**Rule 1 — Always deploy.** When a node/primitive is finalized, deploy it to **BOTH** the Pi package `src` path **and** the `install` path, then restart the node.
**Why:** the Pi was built **without `--symlink-install`**, so editing only `src` does nothing at runtime; the user has repeatedly asked "please for next times always make sure it is deployed."
**How to apply:** for the eventual room-101 executor / hybrid node, push to both paths (a `deploy_all.py`-style step) and confirm the running process picked it up. Local Temp test scripts (drive_yaw.py, exec_seq.py) are the dev loop, but the SHIP step is a deployed node. See [[motion-primitives]].

**Rule 2 — Never move the robot without an explicit "go".** Before ANY command that drives the motors, the user must physically clear the space and say "go" (or equivalent). Announce exactly what motion is about to happen and wait.
**Why:** it's a real robot in a real room; an unexpected lurch can hit people/furniture. The user gates every physical test this way.
**How to apply:** stage the command, state the intended motion (distance/turn), then pause for the user's "go". Never chain a second physical move without a fresh confirmation. Authorization is per-move, not blanket.
