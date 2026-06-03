#!/usr/bin/env python3
"""
goal_relay -- bridge a clicked goal in Foxglove/RViz to Nav2.

Foxglove's 3D "Pose" publish tool (and RViz's GoalTool) put a
geometry_msgs/PoseStamped on /goal_pose. Nav2's core has NO subscriber for that
topic -- in RViz it's the Nav2 *panel plugin* that secretly calls the
navigate_to_pose action. Foxglove has no such plugin, so without this node a
clicked goal goes nowhere. This node restores the behaviour: subscribe to
/goal_pose and forward each pose as a NavigateToPose action goal, so clicking a
goal on the map drives the robot exactly like RViz's "2D Goal Pose".

Standalone script (run via `python3 -u`), matching the imu_mpu9255_node.py
pattern -- no colcon build required.
"""
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


class GoalRelay(Node):
    def __init__(self):
        super().__init__("goal_relay")
        self._ac = ActionClient(self, NavigateToPose, "navigate_to_pose")
        # Listen on BOTH the topic my layout uses (/goal_pose) AND Foxglove's
        # default "Publish pose" topic (/move_base_simple/goal), so a goal click
        # drives the robot no matter which one the publish tool is set to.
        self.sub = self.create_subscription(PoseStamped, "/goal_pose", self.on_goal, 10)
        self.sub2 = self.create_subscription(PoseStamped, "/move_base_simple/goal", self.on_goal, 10)
        self._active = None
        self.get_logger().info(
            "goal_relay up: /goal_pose + /move_base_simple/goal -> navigate_to_pose "
            "(click a goal in Foxglove/RViz to drive)")

    def on_goal(self, msg):
        # Foxglove stamps with the panel's display frame; default to map if blank
        if not msg.header.frame_id:
            msg.header.frame_id = "map"
        if not self._ac.wait_for_server(timeout_sec=2.0):
            self.get_logger().error(
                "navigate_to_pose server not available -- is Nav2 (T3) up?")
            return
        goal = NavigateToPose.Goal()
        goal.pose = msg
        p = msg.pose.position
        self.get_logger().info("Relaying goal -> x=%.3f y=%.3f (frame %s)"
                               % (p.x, p.y, msg.header.frame_id))
        fut = self._ac.send_goal_async(goal, feedback_callback=self._fb)
        fut.add_done_callback(self._accepted)

    def _accepted(self, fut):
        gh = fut.result()
        if not gh.accepted:
            self.get_logger().warn("Goal REJECTED by Nav2")
            return
        self.get_logger().info("Goal accepted; navigating...")
        self._active = gh
        gh.get_result_async().add_done_callback(self._done)

    def _fb(self, fb):
        try:
            d = fb.feedback.distance_remaining
            self.get_logger().info("  ... distance_remaining=%.2f m" % d,
                                   throttle_duration_sec=2.0)
        except Exception:
            pass

    def _done(self, fut):
        status = fut.result().status      # action_msgs/GoalStatus: 4 = SUCCEEDED
        verdict = {4: "SUCCEEDED", 5: "CANCELED", 6: "ABORTED"}.get(status, str(status))
        self.get_logger().info("Goal finished: %s" % verdict)
        self._active = None


def main():
    rclpy.init()
    node = GoalRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
