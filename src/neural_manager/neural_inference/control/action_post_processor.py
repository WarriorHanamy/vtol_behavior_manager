"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Action Post-Processor Component

Converts neural network raw output into PX4-compatible control commands.
Handles action scaling, coordinate transformations, and message formatting.
"""

from __future__ import annotations

import time

import numpy as np
import rclpy.node
from geometry_msgs.msg import Vector3Stamped

from neural_manager.neural_inference.math_utils import frd_flu_rotate
from px4_msgs.msg import VehicleAccRatesSetpoint


class ActionPostProcessor:
  """
  Component responsible for processing raw neural network actions
  into PX4-compatible control commands.

  Outputs VehicleAccRatesSetpoint (thrust acceleration + body rates).
  """

  def __init__(
    self,
    min_thrust_g: float = 0.0,
    max_thrust_g: float = 2.0,
    max_ang_vel: tuple[float, float, float] = (3.0, 5.0, 3.0),
    node_logger=None,
    acc_fixed: bool = False,
    use_tanh_activation: bool = False,
    enable_action_clipping: bool = True,
    action_limits: dict | None = None,
    print_control_commands: bool = False,
    ros_node: rclpy.node.Node | None = None,
  ):
    """
    Initialize the action post-processor.

    Args:
        min_thrust_g: Minimum thrust in g (default 0.0)
        max_thrust_g: Maximum thrust in g (default 2.0)
        max_ang_vel: Maximum angular rates (roll, pitch, yaw) in rad/s
        node_logger: ROS2 node logger for debugging
        acc_fixed: Whether to use fixed thrust acceleration
        use_tanh_activation: Whether to apply tanh activation
        enable_action_clipping: Whether to clip actions to [-1, 1] range
        action_limits: Dictionary containing action limit values
        print_control_commands: Whether to print detailed control command information
        ros_node: ROS2 node for publishing angular rate topics (optional)
    """
    self._min_thrust_g = float(min_thrust_g)
    self._max_thrust_g = float(max_thrust_g)
    self._max_ang_vel = tuple(max_ang_vel)
    self._logger = node_logger
    self._acc_fixed = acc_fixed
    self._use_tanh_activation = use_tanh_activation
    self._enable_action_clipping = enable_action_clipping
    self._print_control_commands = print_control_commands
    self._ros_node = ros_node

    self._angular_rate_flu_pub = None
    self._angular_rate_frd_pub = None
    if ros_node is not None:
      self._angular_rate_flu_pub = ros_node.create_publisher(
        Vector3Stamped, "/neural/angular_rate_command_flu", 10
      )
      self._angular_rate_frd_pub = ros_node.create_publisher(
        Vector3Stamped, "/neural/angular_rate_command_frd", 10
      )
      if self._logger:
         self._logger.info("📡 Action post-processor topic: /neural/angular_rate_command_flu (body_flu)")
        self._logger.info("📡 Action post-processor topic: /neural/angular_rate_command_frd (body_frd)")

    if action_limits is None:
      action_limits = {"min": -1.0, "max": 1.0}
    self._action_limits = action_limits

    self._last_action = np.zeros(4, dtype=np.float32)
    self._last_thrust_acc = 0.0
    self._last_thrust_acc_norm = 0.0
    self._last_frd_ang_vel = np.zeros(3, dtype=np.float32)
    self._last_flu_ang_vel = np.zeros(3, dtype=np.float32)
    self._control_command_count = 0

    if self._logger:
      self._logger.info(
        "🎮 动作后处理器模式: Thrust Acceleration + Body Rates (VehicleAccRatesSetpoint)"
      )

  def process_action(self, raw_action: np.ndarray) -> VehicleAccRatesSetpoint:
    """
    Process raw neural network action into PX4 control message.

    Args:
        raw_action: Raw action from neural network [thrust, roll_rate, pitch_rate, yaw_rate]

    Returns:
        VehicleAccRatesSetpoint message
    """
    if raw_action.shape != (4,):
      if self._logger:
        self._logger.error(f"Invalid action shape: {raw_action.shape}, expected (4,)")
      raw_action = np.zeros(4, dtype=np.float32)

    action = raw_action.astype(np.float32)

    if self._use_tanh_activation:
      action = np.tanh(action)
    elif self._enable_action_clipping:
      action = np.clip(action, self._action_limits["min"], self._action_limits["max"])

    self._last_action = action.copy()

    thrust_raw = action[0]
    roll_rate_raw = action[1]
    pitch_rate_raw = action[2]
    yaw_rate_raw = action[3]

    roll_rate = roll_rate_raw * self._max_ang_vel[0]
    pitch_rate = pitch_rate_raw * self._max_ang_vel[1]
    yaw_rate = yaw_rate_raw * self._max_ang_vel[2]

    flu_ang_vel = np.array([roll_rate, pitch_rate, yaw_rate])
    frd_ang_vel = frd_flu_rotate(flu_ang_vel)

    self._last_thrust_acc_norm = thrust_raw
    self._last_flu_ang_vel = flu_ang_vel.copy()

    self._publish_angular_rates(flu_ang_vel, frd_ang_vel)

    return self._create_acc_rates_message(thrust_raw, frd_ang_vel)

  def _create_acc_rates_message(
    self, thrust_raw: float, frd_ang_vel: np.ndarray
  ) -> VehicleAccRatesSetpoint:
    """
    Create VehicleAccRatesSetpoint message.

    Args:
        thrust_raw: Normalized thrust acceleration [-1, 1]
        frd_ang_vel: Body rates in FRD frame [roll, pitch, yaw] rad/s

    Returns:
        VehicleAccRatesSetpoint message
    """
    msg = VehicleAccRatesSetpoint()
    msg.timestamp = int(time.time() * 1e6)

    thrust_acc = self._convert_thrust_to_acceleration(thrust_raw)
    msg.thrust_axis_acc_sp = float(thrust_acc)

    msg.rates_sp[0] = float(frd_ang_vel[0])
    msg.rates_sp[1] = float(frd_ang_vel[1])
    msg.rates_sp[2] = float(frd_ang_vel[2])

    self._last_thrust_acc = float(thrust_acc)
    self._last_frd_ang_vel = frd_ang_vel.copy()

    msg.sol_time = -1.0

    if self._print_control_commands:
      direction = "↑ UP" if thrust_acc < 0 else ("↓ DOWN" if thrust_acc > 0 else "— ZERO")
      self._logger.info(
        f"VehicleAccRatesSetpoint: thrust_axis_acc_sp={thrust_acc:+.3f} m/s² ({direction}), "
        f"rates_sp=[{frd_ang_vel[0]:+.3f}, {frd_ang_vel[1]:+.3f}, {frd_ang_vel[2]:+.3f}] rad/s (FRD)"
      )

    return msg

  def _publish_angular_rates(self, flu_ang_vel: np.ndarray, frd_ang_vel: np.ndarray):
    """
    Publish angular rate commands in both FLU and FRD coordinate frames.

    Args:
        flu_ang_vel: Angular rates in FLU (body) frame [roll, pitch, yaw] rad/s
        frd_ang_vel: Angular rates in FRD (PX4 body) frame [roll, pitch, yaw] rad/s
    """
    if self._angular_rate_flu_pub is None or self._angular_rate_frd_pub is None:
      return

    timestamp = time.time()

    msg_flu = Vector3Stamped()
    msg_flu.header.stamp.sec = int(timestamp)
    msg_flu.header.stamp.nanosec = int((timestamp - int(timestamp)) * 1e9)
    msg_flu.header.frame_id = "body_flu"
    msg_flu.vector.x = float(flu_ang_vel[0])
    msg_flu.vector.y = float(flu_ang_vel[1])
    msg_flu.vector.z = float(flu_ang_vel[2])
    self._angular_rate_flu_pub.publish(msg_flu)

    msg_frd = Vector3Stamped()
    msg_frd.header.stamp.sec = int(timestamp)
    msg_frd.header.stamp.nanosec = int((timestamp - int(timestamp)) * 1e9)
    msg_frd.header.frame_id = "body_frd"
    msg_frd.vector.x = float(frd_ang_vel[0])
    msg_frd.vector.y = float(frd_ang_vel[1])
    msg_frd.vector.z = float(frd_ang_vel[2])
    self._angular_rate_frd_pub.publish(msg_frd)

  def _convert_thrust_to_acceleration(self, thrust_raw: float) -> float:
    """
    Convert normalized thrust to acceleration in m/s^2.

    Follows training convention (actions_cl_torque.py):
    - Map [-1, 1] → [min_thrust_g, max_thrust_g]
    - thrust_raw = -1 → 0g (falling)
    - thrust_raw =  0 → 1g (hover)
    - thrust_raw = +1 → 2g (climbing)

    PX4 thrust_axis_acc_sp: down-positive, so negate at the end.

    Args:
        thrust_raw: Normalized thrust value [-1, 1] (after tanh activation)

    Returns:
        Thrust acceleration in m/s^2 (down positive, up negative)
    """
    G = 9.81
    if self._acc_fixed:
      return float(-G)

    thrust_g = ((thrust_raw + 1.0) / 2.0) * (
      self._max_thrust_g - self._min_thrust_g
    ) + self._min_thrust_g
    thrust_acc = -thrust_g * G

    return float(thrust_acc)

  def get_action_limits(self) -> dict:
    """
    Get the current action limits.

    Returns:
        Dictionary containing action limit configuration
    """
    return {
      "min": self._action_limits["min"],
      "max": self._action_limits["max"],
      "min_thrust_g": self._min_thrust_g,
      "max_thrust_g": self._max_thrust_g,
      "max_ang_vel": self._max_ang_vel,
      "acc_fixed": self._acc_fixed,
      "use_tanh_activation": self._use_tanh_activation,
      "enable_action_clipping": self._enable_action_clipping,
      "print_control_commands": self._print_control_commands,
      "ros_node": self._ros_node,
    }

  def get_last_action(self) -> np.ndarray:
    """
    Get the last processed action.

    Returns:
        Last action array [thrust, roll_rate, pitch_rate, yaw_rate]
    """
    return self._last_action.copy()

  def get_last_output(self) -> dict:
    """
    Get the last output values for logging.

    Returns:
        Dictionary containing:
        - thrust_acc: Thrust acceleration in m/s^2
        - thrust_acc_norm: Normalized thrust acceleration [-1, 1]
        - frd_ang_vel: Angular rates in FRD frame [roll, pitch, yaw] rad/s
        - flu_ang_vel: Angular rates in FLU frame [roll, pitch, yaw] rad/s
    """
    return {
      "thrust_acc": self._last_thrust_acc,
      "thrust_acc_norm": self._last_thrust_acc_norm,
      "frd_ang_vel": self._last_frd_ang_vel.copy(),
      "flu_ang_vel": self._last_flu_ang_vel.copy(),
    }

  def convert_action_for_display(self, raw_action: np.ndarray) -> dict:
    """
    Convert action for human-readable display.

    Args:
        raw_action: Raw action from neural network

    Returns:
        Dictionary with formatted action values for printing
    """
    if self._use_tanh_activation:
      action = np.tanh(raw_action)
    elif self._enable_action_clipping:
      action = np.clip(raw_action, self._action_limits["min"], self._action_limits["max"])
    else:
      action = raw_action.astype(np.float32)

    thrust_raw = action[0]
    roll_rate_raw = action[1]
    pitch_rate_raw = action[2]
    yaw_rate_raw = action[3]

    roll_rate = roll_rate_raw * self._max_ang_vel[0]
    pitch_rate = pitch_rate_raw * self._max_ang_vel[1]
    yaw_rate = yaw_rate_raw * self._max_ang_vel[2]

    thrust_acc = self._convert_thrust_to_acceleration(thrust_raw)
    return {
      "control_mode": "acc_rates",
      "thrust_acc": thrust_acc,
      "thrust_raw": thrust_raw,
      "roll_rate": roll_rate,
      "roll_rate_raw": roll_rate_raw,
      "pitch_rate": pitch_rate,
      "pitch_rate_raw": pitch_rate_raw,
      "yaw_rate": yaw_rate,
      "yaw_rate_raw": yaw_rate_raw,
    }

  def print_control_command(self, action_display_dict: dict, prefix: str = ""):
    """
    Print control command in human-readable format.

    Args:
        action_display_dict: Dictionary with formatted action values from convert_action_for_display
        prefix: Optional prefix string for the output
    """
    if not self._print_control_commands or action_display_dict is None:
      return

    self._control_command_count += 1

    print(f"{prefix}🎮 控制指令 #{self._control_command_count} (4维) [推力加速度模式]:")
    thrust_acc = action_display_dict["thrust_acc"]
    thrust_raw = action_display_dict["thrust_raw"]
    print(f"{prefix}  ⬆️  推力加速度:     {thrust_acc:.3f} m/s² (原始: {thrust_raw:.3f})")
    roll_rate = action_display_dict["roll_rate"]
    roll_rate_raw = action_display_dict["roll_rate_raw"]
    print(f"{prefix}  🔄 Roll rate:     {roll_rate:.3f} rad/s (raw: {roll_rate_raw:.3f})")
    pitch_rate = action_display_dict["pitch_rate"]
    pitch_rate_raw = action_display_dict["pitch_rate_raw"]
    print(f"{prefix}  🔄 俯仰角速度:     {pitch_rate:.3f} rad/s (原始: {pitch_rate_raw:.3f})")
    yaw_rate = action_display_dict["yaw_rate"]
    yaw_rate_raw = action_display_dict["yaw_rate_raw"]
    print(f"{prefix}  🔄 偏航角速度:     {yaw_rate:.3f} rad/s (原始: {yaw_rate_raw:.3f})")

  def validate_action(self, raw_action: np.ndarray) -> bool:
    """
    Validate action shape and values.

    Args:
        raw_action: Raw action to validate

    Returns:
        True if action is valid, False otherwise
    """
    if raw_action.shape != (4,):
      if self._logger:
        self._logger.warning(f"Invalid action shape: {raw_action.shape}")
      return False

    if not np.all(np.isfinite(raw_action)):
      if self._logger:
        self._logger.warning(f"Invalid action values (NaN/Inf): {raw_action}")
      return False

    if self._use_tanh_activation:
      processed_action = np.tanh(raw_action)
      if not np.all(np.isfinite(processed_action)):
        if self._logger:
          self._logger.warning(f"Invalid action after tanh: {processed_action}")
        return False
    elif self._enable_action_clipping:
      clipped_action = np.clip(raw_action, self._action_limits["min"], self._action_limits["max"])
      if not np.allclose(raw_action, clipped_action, atol=1e-6):
        if self._logger:
          self._logger.debug(f"Action clipped from {raw_action} to {clipped_action}")

    return True

  def get_processor_info(self) -> dict:
    """
    Get processor information for debugging.

    Returns:
        Dictionary containing processor configuration and state
    """
    return {
      "min_thrust_g": self._min_thrust_g,
      "max_thrust_g": self._max_thrust_g,
      "max_ang_vel": self._max_ang_vel,
      "acc_fixed": self._acc_fixed,
      "last_action": self._last_action.tolist(),
    }

  def reset(self):
    """Reset processor state for fresh start."""
    self._last_action = np.zeros(4, dtype=np.float32)
    self._last_thrust_acc = 0.0
    self._last_frd_ang_vel = np.zeros(3, dtype=np.float32)
    self._control_command_count = 0 