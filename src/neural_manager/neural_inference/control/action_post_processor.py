#!/usr/bin/env python3
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
from typing import Optional

import numpy as np
import rclpy.node
from geometry_msgs.msg import Vector3Stamped
from px4_msgs.msg import VehicleRatesSetpoint, VehicleThrustAccSetpoint

from transforms.math_utils import frd_flu_rotate


class ActionPostProcessor:
    """
    Component responsible for processing raw neural network actions
    into PX4-compatible control messages.

    Supports two control modes (configurable):
    1. 'throttle_rates': Throttle + body rates (VehicleRatesSetpoint) - for multicopters
    2. 'acc_rates': Thrust acceleration + body rates (VehicleThrustAccSetpoint) - alternative mode
    """

    def __init__(
        self,
        control_mode: str = "throttle_rates",
        max_acc: float = 19.62,
        max_roll_pitch_rate: float = 1.0,
        max_yaw_rate: float = 1.0,
        node_logger=None,
        acc_fixed: bool = False,
        use_tanh_activation: bool = True,
        enable_action_clipping: bool = False,
        action_limits: Optional[dict] = None,
        print_control_commands: bool = False,
        ros_node: Optional[rclpy.node.Node] = None,
    ):
        """
        Initialize the action post-processor.

        Args:
            control_mode: Control mode - 'throttle_rates' or 'acc_rates'
            max_acc: Maximum acceleration in m/s^2 (only for rates_acc mode, default 2*g)
            max_roll_pitch_rate: Maximum roll/pitch angular rate in rad/s
            max_yaw_rate: Maximum yaw angular rate in rad/s
            node_logger: ROS2 node logger for debugging
            acc_fixed: Whether to use fixed thrust acceleration (only for rates_acc mode)
            use_tanh_activation: Whether to apply tanh activation (default True, matching training)
            enable_action_clipping: Whether to clip actions to [-1, 1] range (deprecated, use tanh instead)
            action_limits: Dictionary containing action limit values
            print_control_commands: Whether to print detailed control command information
            ros_node: ROS2 node for publishing angular rate topics (optional)
        """
        self._control_mode = control_mode.lower()
        if self._control_mode not in ["throttle_rates", "acc_rates"]:
            raise ValueError(
                f"Invalid control_mode '{control_mode}'. Must be 'throttle_rates' or 'acc_rates'"
            )

        self._max_acc = float(max_acc)
        self._max_roll_pitch_rate = float(max_roll_pitch_rate)
        self._max_yaw_rate = float(max_yaw_rate)
        self._logger = node_logger
        self._acc_fixed = acc_fixed
        self._use_tanh_activation = use_tanh_activation
        self._enable_action_clipping = enable_action_clipping
        self._print_control_commands = print_control_commands

        # Create ROS2 publishers for angular rate commands (FLU and FRD frames)
        self._angular_rate_flu_pub = None
        self._angular_rate_frd_pub = None
        self._throttle_pub = None
        if ros_node is not None:
            from std_msgs.msg import Float32

            self._angular_rate_flu_pub = ros_node.create_publisher(
                Vector3Stamped, "/neural/angular_rate_command_flu", 10
            )
            self._angular_rate_frd_pub = ros_node.create_publisher(
                Vector3Stamped, "/neural/angular_rate_command_frd", 10
            )
            self._throttle_pub = ros_node.create_publisher(
                Float32, "/neural/throttle_command", 10
            )
            if self._logger:
                self._logger.info(
                    "📡 动作后处理器话题: /neural/angular_rate_command_flu (body_flu)"
                )
                self._logger.info(
                    "📡 动作后处理器话题: /neural/angular_rate_command_frd (body_frd)"
                )
                self._logger.info(
                    "📡 动作后处理器话题: /neural/throttle_command (throttle)"
                )

        # Default action limits (only used if clipping is enabled)
        if action_limits is None:
            action_limits = {"min": -1.0, "max": 1.0}
        self._action_limits = action_limits

        # Store last action for debugging/continuity
        self._last_action = np.zeros(4, dtype=np.float32)

        # Control command count for logging
        self._control_command_count = 0

        # Log control mode
        if self._logger:
            mode_name = (
                "Throttle + Body Rates (VehicleRatesSetpoint)"
                if self._control_mode == "throttle_rates"
                else "Thrust Acceleration + Body Rates (VehicleThrustAccSetpoint)"
            )
            self._logger.info(f"🎮 动作后处理器模式: {mode_name}")

    def process_action(self, raw_action: np.ndarray):
        """
        Process raw neural network action into PX4 control message.

        Args:
            raw_action: Raw action from neural network [thrust/throttle, roll_rate, pitch_rate, yaw_rate]

        Returns:
            VehicleRatesSetpoint or VehicleThrustAccSetpoint message based on control_mode
        """
        # Ensure action is the right shape and type
        if raw_action.shape != (4,):
            if self._logger:
                self._logger.error(
                    f"Invalid action shape: {raw_action.shape}, expected (4,)"
                )
            # Fallback to zeros
            raw_action = np.zeros(4, dtype=np.float32)

        # Convert to float32 if needed
        action = raw_action.astype(np.float32)

        # Apply tanh activation to map MLP output to [-1, 1] (matching training environment)
        # This is smoother and more gradient-friendly than hard clipping
        if self._use_tanh_activation:
            action = np.tanh(action)
        elif self._enable_action_clipping:
            # Fallback to hard clipping (deprecated, use tanh instead)
            action = np.clip(
                action, self._action_limits["min"], self._action_limits["max"]
            )

        # Store for next iteration
        self._last_action = action.copy()

        # Extract and scale action components
        thrust_or_throttle_raw = action[0]  # Normalized thrust/throttle [-1, 1]
        roll_rate_raw = action[1]  # Normalized roll rate [-1, 1]
        pitch_rate_raw = action[2]  # Normalized pitch rate [-1, 1]
        yaw_rate_raw = action[3]  # Normalized yaw rate [-1, 1]

        # Convert angular rates to actual values
        roll_rate = roll_rate_raw * self._max_roll_pitch_rate
        pitch_rate = pitch_rate_raw * self._max_roll_pitch_rate
        yaw_rate = yaw_rate_raw * self._max_yaw_rate

        # Convert angular rates from FLU to FRD coordinate system
        rate_flu = np.array([roll_rate, pitch_rate, yaw_rate])
        rate_frd = frd_flu_rotate(rate_flu)

        # Publish angular rate commands to ROS2 topics
        self._publish_angular_rates(rate_flu, rate_frd)

        # Create message based on control mode
        if self._control_mode == "throttle_rates":
            return self._create_rates_throttle_message(thrust_or_throttle_raw, rate_frd)
        else:  # acc_rates
            return self._create_rates_acc_message(thrust_or_throttle_raw, rate_frd)

    def _create_rates_throttle_message(
        self, throttle_raw: float, rate_frd: np.ndarray
    ) -> VehicleRatesSetpoint:
        """
        Create VehicleRatesSetpoint message (throttle + body rates).

        Args:
            throttle_raw: Normalized throttle [-1, 1]
            rate_frd: Body rates in FRD frame [roll, pitch, yaw] rad/s

        Returns:
            VehicleRatesSetpoint message
        """
        msg = VehicleRatesSetpoint()
        msg.timestamp = int(time.time() * 1e6)  # Convert to microseconds

        # Populate rate setpoints
        # Populate rate setpoints
        msg.roll = float(rate_frd[0])  # Roll rate (FRD)
        msg.pitch = float(rate_frd[1])  # Pitch rate (FRD)
        msg.yaw = float(rate_frd[2])  # Yaw rate (FRD)

        # Populate thrust_body for multicopters
        # For multicopters: thrust_body[0] and [1] are 0, [2] is negative throttle
        throttle = self._convert_throttle(throttle_raw)
        msg.thrust_body[0] = 0.0
        msg.thrust_body[1] = 0.0
        msg.thrust_body[2] = float(
            throttle
        )  # Negative throttle demand (NED Z-axis down)

        # Publish throttle value to ROS2 topic
        self._publish_throttle(throttle)

        msg.reset_integral = False

        return msg

    def _create_rates_acc_message(
        self, thrust_acc_raw: float, rate_frd: np.ndarray
    ) -> VehicleThrustAccSetpoint:
        """
        Create VehicleThrustAccSetpoint message (thrust acceleration + body rates).

        Args:
            thrust_acc_raw: Normalized thrust acceleration [-1, 1]
            rate_frd: Body rates in FRD frame [roll, pitch, yaw] rad/s

        Returns:
            VehicleThrustAccSetpoint message
        """
        msg = VehicleThrustAccSetpoint()
        msg.timestamp = int(time.time() * 1e6)  # Convert to microseconds

        # Convert thrust to acceleration
        thrust_acc = self._convert_thrust_to_acceleration(thrust_acc_raw)
        msg.thrust_acc_sp = float(thrust_acc)

        # Populate rate setpoints (already in FRD)
        msg.rates_sp[0] = float(rate_frd[0])  # Roll rate
        msg.rates_sp[1] = float(rate_frd[1])  # Pitch rate
        msg.rates_sp[2] = float(rate_frd[2])  # Yaw rate

        return msg

    def _publish_angular_rates(self, rate_flu: np.ndarray, rate_frd: np.ndarray):
        """
        Publish angular rate commands in both FLU and FRD coordinate frames.

        Args:
            rate_flu: Angular rates in FLU (body) frame [roll, pitch, yaw] rad/s
            rate_frd: Angular rates in FRD (PX4 body) frame [roll, pitch, yaw] rad/s
        """
        if self._angular_rate_flu_pub is None or self._angular_rate_frd_pub is None:
            return

        timestamp = time.time()

        # Publish FLU angular rates (network output frame)
        msg_flu = Vector3Stamped()
        msg_flu.header.stamp.sec = int(timestamp)
        msg_flu.header.stamp.nanosec = int((timestamp - int(timestamp)) * 1e9)
        msg_flu.header.frame_id = "body_flu"
        msg_flu.vector.x = float(rate_flu[0])  # Roll rate
        msg_flu.vector.y = float(rate_flu[1])  # Pitch rate
        msg_flu.vector.z = float(rate_flu[2])  # Yaw rate
        self._angular_rate_flu_pub.publish(msg_flu)

        # Publish FRD angular rates (PX4 command frame)
        msg_frd = Vector3Stamped()
        msg_frd.header.stamp.sec = int(timestamp)
        msg_frd.header.stamp.nanosec = int((timestamp - int(timestamp)) * 1e9)
        msg_frd.header.frame_id = "body_frd"
        msg_frd.vector.x = float(rate_frd[0])  # Roll rate
        msg_frd.vector.y = float(rate_frd[1])  # Pitch rate
        msg_frd.vector.z = float(rate_frd[2])  # Yaw rate
        self._angular_rate_frd_pub.publish(msg_frd)

    def _publish_throttle(self, throttle: float):
        """
        Publish throttle command value.

        Args:
            throttle: Throttle value (negative, for body NED frame Z-axis)
        """
        if self._throttle_pub is None:
            return

        from std_msgs.msg import Float32

        msg = Float32()
        msg.data = float(throttle)
        self._throttle_pub.publish(msg)

    def _convert_throttle(self, throttle_raw: float) -> float:
        """
        Convert normalized throttle to PX4 thrust_body[2] value.

        Args:
            throttle_raw: Normalized throttle value [-1, 1]

        Returns:
            Throttle value (negative, for body NED frame Z-axis)
        """
        # Map [-1, 1] to throttle range
        # throttle_raw = -1 -> min throttle (0.0)
        # throttle_raw = 0  -> ~50% throttle (-0.5)
        # throttle_raw = 1  -> max throttle (-1.0)

        # Map to [-1, 0] range (negative for downward thrust in body NED)
        throttle = -(throttle_raw + 1.0) / 2.0  # Maps [-1,1] to [-1, 0]

        # Clamp to valid range
        throttle = np.clip(throttle, -1.0, 0.0)

        return float(throttle)

    def _convert_thrust_to_acceleration(self, thrust_raw: float) -> float:
        """
        Convert normalized thrust to acceleration in m/s^2.

        Args:
            thrust_raw: Normalized thrust value [-1, 1] (after tanh activation)

        Returns:
            Thrust acceleration in m/s^2
        """
        if self._acc_fixed:
            # Fixed acceleration mode (hover at ~50% of max)
            return float(self._max_acc / 2.0)

        # Map thrust_raw from [-1, 1] to [0, 1] (matching isaac_drone_ctrl processing)
        # thrust_raw = -1 -> 0.0
        # thrust_raw =  0 -> 0.5
        # thrust_raw =  1 -> 1.0
        thrust_frac = (thrust_raw + 1.0) / 2.0
        thrust_frac = np.clip(thrust_frac, 0.0, 1.0)

        # Scale to [0, max_acc]
        # max_acc = maximum acceleration (e.g., 19.62 m/s^2 = 2*g)
        thrust_acc = thrust_frac * self._max_acc

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
            "max_acc": self._max_acc,
            "max_roll_pitch_rate": self._max_roll_pitch_rate,
            "max_yaw_rate": self._max_yaw_rate,
            "acc_fixed": self._acc_fixed,
        }

    def get_last_action(self) -> np.ndarray:
        """
        Get the last processed action.

        Returns:
            Last action array [thrust, roll_rate, pitch_rate, yaw_rate]
        """
        return self._last_action.copy()

    def convert_action_for_display(self, raw_action: np.ndarray) -> dict:
        """
        Convert action for human-readable display.

        Args:
            raw_action: Raw action from neural network

        Returns:
            Dictionary with formatted action values for printing
        """
        # Apply action processing for display (same as in process_action)
        if self._use_tanh_activation:
            action = np.tanh(raw_action)
        elif self._enable_action_clipping:
            action = np.clip(
                raw_action, self._action_limits["min"], self._action_limits["max"]
            )
        else:
            action = raw_action.astype(np.float32)

        # Extract components
        thrust_raw = action[0]
        roll_rate_raw = action[1]
        pitch_rate_raw = action[2]
        yaw_rate_raw = action[3]

        # Convert to actual values
        roll_rate = roll_rate_raw * self._max_roll_pitch_rate
        pitch_rate = pitch_rate_raw * self._max_roll_pitch_rate
        yaw_rate = yaw_rate_raw * self._max_yaw_rate

        # Convert thrust based on control mode
        if self._control_mode == "throttle_rates":
            throttle = self._convert_throttle(thrust_raw)
            return {
                "control_mode": "throttle_rates",
                "throttle": throttle,
                "throttle_raw": thrust_raw,
                "roll_rate": roll_rate,
                "roll_rate_raw": roll_rate_raw,
                "pitch_rate": pitch_rate,
                "pitch_rate_raw": pitch_rate_raw,
                "yaw_rate": yaw_rate,
                "yaw_rate_raw": yaw_rate_raw,
            }
        else:  # acc_rates
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

        control_mode = action_display_dict.get("control_mode", "acc_rates")

        if control_mode == "throttle_rates":
            # Display throttle mode
            print(
                f"{prefix}🎮 控制指令 #{self._control_command_count} (4维) [Throttle模式]:"
            )
            print(
                f"{prefix}  ⬆️  油门:           {action_display_dict['throttle']:.3f} (归一化, 原始: {action_display_dict['throttle_raw']:.3f})"
            )
            print(
                f"{prefix}  🔄 横滚角速度:     {action_display_dict['roll_rate']:.3f} rad/s (原始: {action_display_dict['roll_rate_raw']:.3f})"
            )
            print(
                f"{prefix}  🔄 俯仰角速度:     {action_display_dict['pitch_rate']:.3f} rad/s (原始: {action_display_dict['pitch_rate_raw']:.3f})"
            )
            print(
                f"{prefix}  🔄 偏航角速度:     {action_display_dict['yaw_rate']:.3f} rad/s (原始: {action_display_dict['yaw_rate_raw']:.3f})"
            )
        else:  # rates_acc
            # Display thrust acceleration mode
            print(
                f"{prefix}🎮 控制指令 #{self._control_command_count} (4维) [推力加速度模式]:"
            )
            print(
                f"{prefix}  ⬆️  推力加速度:     {action_display_dict['thrust_acc']:.3f} m/s² (原始: {action_display_dict['thrust_raw']:.3f})"
            )
            print(
                f"{prefix}  🔄 横滚角速度:     {action_display_dict['roll_rate']:.3f} rad/s (原始: {action_display_dict['roll_rate_raw']:.3f})"
            )
            print(
                f"{prefix}  🔄 俯仰角速度:     {action_display_dict['pitch_rate']:.3f} rad/s (原始: {action_display_dict['pitch_rate_raw']:.3f})"
            )
            print(
                f"{prefix}  🔄 偏航角速度:     {action_display_dict['yaw_rate']:.3f} rad/s (原始: {action_display_dict['yaw_rate_raw']:.3f})"
            )

    def validate_action(self, raw_action: np.ndarray) -> bool:
        """
        Validate action shape and values.

        Args:
            raw_action: Raw action to validate

        Returns:
            True if action is valid, False otherwise
        """
        # Check shape
        if raw_action.shape != (4,):
            if self._logger:
                self._logger.warning(f"Invalid action shape: {raw_action.shape}")
            return False

        # Check for NaN or infinite values
        if not np.all(np.isfinite(raw_action)):
            if self._logger:
                self._logger.warning(f"Invalid action values (NaN/Inf): {raw_action}")
            return False

        # Check for extreme values (after processing)
        if self._use_tanh_activation:
            # tanh naturally bounds to [-1, 1], just check for NaN after tanh
            processed_action = np.tanh(raw_action)
            if not np.all(np.isfinite(processed_action)):
                if self._logger:
                    self._logger.warning(
                        f"Invalid action after tanh: {processed_action}"
                    )
                return False
        elif self._enable_action_clipping:
            clipped_action = np.clip(
                raw_action, self._action_limits["min"], self._action_limits["max"]
            )
            if not np.allclose(raw_action, clipped_action, atol=1e-6):
                if self._logger:
                    self._logger.debug(
                        f"Action clipped from {raw_action} to {clipped_action}"
                    )

        return True

    def get_processor_info(self) -> dict:
        """
        Get processor information for debugging.

        Returns:
            Dictionary containing processor configuration and state
        """
        return {
            "max_acc": self._max_acc,
            "max_roll_pitch_rate": self._max_roll_pitch_rate,
            "max_yaw_rate": self._max_yaw_rate,
            "acc_fixed": self._acc_fixed,
            "use_tanh_activation": self._use_tanh_activation,
            "action_clipping_enabled": self._enable_action_clipping,
            "action_limits": self._action_limits,
            "last_action": self._last_action.tolist(),
        }

    def reset(self):
        """Reset processor state for fresh start."""
        self._last_action = np.zeros(4, dtype=np.float32)
        self._control_command_count = 0
