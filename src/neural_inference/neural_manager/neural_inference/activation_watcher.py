#!/usr/bin/env python3
"""Subscribe to /neural/target and trigger 'activate' lifecycle transition.

This node watches for the first NeuralTarget message, then calls
'ros2 lifecycle set /neural_infer_node activate' to transition the
inference node from inactive to active.

Designed to be launched alongside the lifecycle inference node.
"""

from __future__ import annotations

import subprocess

import rclpy
from rclpy.node import Node

from goal_msgs.msg import NeuralTarget


class ActivationWatcher(Node):
  """Listens for first NeuralTarget, triggers lifecycle activate."""

  def __init__(self):
    super().__init__("neural_activation_watcher")
    self._done = False
    self._sub = self.create_subscription(NeuralTarget, "/neural/target", self._on_target, 10)
    self.get_logger().info("Watching /neural/target for lifecycle activation...")

  def _on_target(self, msg: NeuralTarget) -> None:
    if self._done:
      return
    self._done = True
    self.get_logger().info(f"Target received (task_type={msg.task_type}). Triggering activate...")
    try:
      result = subprocess.run(
        ["ros2", "lifecycle", "set", "/neural_infer_node", "activate"],
        capture_output=True,
        text=True,
        timeout=5,
      )
      self.get_logger().info(result.stdout.strip())
      if result.returncode != 0:
        self.get_logger().error(result.stderr.strip())
      else:
        self.get_logger().info("Infer node activated.")
    except Exception as e:
      self.get_logger().error(f"Failed to activate: {e}")


def main():
  rclpy.init()
  watcher = ActivationWatcher()
  try:
    rclpy.spin(watcher)
  except KeyboardInterrupt:
    pass
  finally:
    watcher.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
  main()
