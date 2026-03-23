#!/usr/bin/env python3
"""
Joystick Readiness Probe for Test Executor

This script checks if manual control input is valid before starting the test executor.
The readiness signal is currently based on ManualControlInput::buttons() availability.

This probe is isolated to allow future changes to the readiness signal without
modifying the service flow.

Usage:
    python3 joystick_readiness_probe.py [--timeout TIMEOUT_SECONDS]

Exit codes:
    0: Joystick is ready (manual control input is valid)
    1: Joystick not ready or timeout exceeded
    2: Invalid arguments or error
"""

import argparse
import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import Header

from px4_msgs.msg import ManualControlSetpoint


class JoystickReadinessProbe(Node):
  """
  Probe node that checks if manual control input is valid.

  The current readiness signal is based on receiving valid manual control
  setpoint messages with non-zero buttons data.
  """

  def __init__(self, timeout_seconds: float = 5.0):
    super().__init__("joystick_readiness_probe")
    self.timeout_seconds = timeout_seconds
    self.ready = False
    self.start_time = self.get_clock().now()

    # Subscribe to manual control setpoint topic
    # This corresponds to ManualControlInput::buttons() availability
    self.subscription = self.create_subscription(
      ManualControlSetpoint, "/fmu/in/manual_control_setpoint", self.manual_control_callback, 10
    )

    self.get_logger().info(f"Joystick readiness probe started with {timeout_seconds}s timeout")

  def manual_control_callback(self, msg: ManualControlSetpoint):
    """
    Callback for manual control setpoint messages.

    Current readiness check: message must be valid and have buttons data available.
    This corresponds to _manual_control_input->buttons() availability.

    FUTURE: Modify this function to change the readiness signal without
            modifying the service flow or probe exit conditions.
    """
    # Check if manual control is valid
    if msg.valid:
      # Current readiness signal: buttons() is available
      # This is isolated here for easy future modification
      if msg.buttons is not None and msg.buttons != 0:
        self.ready = True
        self.get_logger().info(f"Joystick ready: valid manual control with buttons={msg.buttons}")
        self.get_logger().info("Readiness signal: _manual_control_input->buttons() availability")
      else:
        self.get_logger().warn(f"Manual control valid but buttons not ready: buttons={msg.buttons}")
    else:
      self.get_logger().warn("Manual control setpoint not valid yet")

  def check_readiness(self) -> bool:
    """
    Check if joystick is ready within timeout period.

    Returns:
        True if ready, False otherwise
    """
    # Spin with timeout
    while rclpy.ok() and not self.ready:
      rclpy.spin_once(self, timeout_sec=0.1)

      # Check timeout
      elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1e9
      if elapsed >= self.timeout_seconds:
        self.get_logger().error(f"Joystick readiness timeout after {elapsed:.1f}s")
        return False

    return self.ready


def main():
  parser = argparse.ArgumentParser(description="Probe to check if joystick is ready before starting test executor")
  parser.add_argument(
    "--timeout", type=float, default=5.0, help="Timeout in seconds to wait for joystick readiness (default: 5.0)"
  )

  args = parser.parse_args()

  if args.timeout <= 0:
    print("Error: timeout must be positive", file=sys.stderr)
    return 2

  # Initialize ROS2
  rclpy.init()

  try:
    probe = JoystickReadinessProbe(timeout_seconds=args.timeout)
    ready = probe.check_readiness()

    if ready:
      print("Joystick ready: manual control input is valid")
      return 0
    else:
      print("Joystick not ready: manual control input is not valid", file=sys.stderr)
      return 1

  except KeyboardInterrupt:
    print("\nProbe interrupted", file=sys.stderr)
    return 1
  except Exception as e:
    print(f"Probe error: {e}", file=sys.stderr)
    return 2
  finally:
    rclpy.shutdown()


if __name__ == "__main__":
  sys.exit(main())
