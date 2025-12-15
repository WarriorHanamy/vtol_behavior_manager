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
from px4_msgs.msg import VehicleThrustAccSetpoint

from .math_utils import frd_flu_rotate


class ActionPostProcessor:
    """
    Component responsible for processing raw neural network actions
    into PX4-compatible VehicleThrustAccSetpoint messages.
    """

    def __init__(
        self,
        thrust_acc_base: float = 9.81,
        max_roll_pitch_rate: float = 1.0,
        max_yaw_rate: float = 1.0,
        node_logger = None,
        acc_fixed: bool = False,
        enable_action_clipping: bool = True,
        action_limits: Optional[dict] = None,
        print_control_commands: bool = False,
    ):
        """
        Initialize the action post-processor.

        Args:
            thrust_acc_base: Base thrust acceleration in m/s^2
            max_roll_pitch_rate: Maximum roll/pitch angular rate in rad/s
            max_yaw_rate: Maximum yaw angular rate in rad/s
            node_logger: ROS2 node logger for debugging
            acc_fixed: Whether to use fixed thrust acceleration
            enable_action_clipping: Whether to clip actions to [-1, 1] range
            action_limits: Dictionary containing action limit values
            print_control_commands: Whether to print detailed control command information
        """
        self._thrust_acc_base = float(thrust_acc_base)
        self._max_roll_pitch_rate = float(max_roll_pitch_rate)
        self._max_yaw_rate = float(max_yaw_rate)
        self._logger = node_logger
        self._acc_fixed = acc_fixed
        self._enable_action_clipping = enable_action_clipping
        self._print_control_commands = print_control_commands

        # Default action limits
        if action_limits is None:
            action_limits = {
                "min": -1.0,
                "max": 1.0
            }
        self._action_limits = action_limits

        # Store last action for debugging/continuity
        self._last_action = np.zeros(4, dtype=np.float32)

        # Control command count for logging
        self._control_command_count = 0

    def process_action(self, raw_action: np.ndarray) -> VehicleThrustAccSetpoint:
        """
        Process raw neural network action into PX4 control message.

        Args:
            raw_action: Raw action from neural network [thrust, roll_rate, pitch_rate, yaw_rate]

        Returns:
            VehicleThrustAccSetpoint message ready for publishing
        """
        # Ensure action is the right shape and type
        if raw_action.shape != (4,):
            if self._logger:
                self._logger.error(f"Invalid action shape: {raw_action.shape}, expected (4,)")
            # Fallback to zeros
            raw_action = np.zeros(4, dtype=np.float32)

        # Convert to float32 if needed
        action = raw_action.astype(np.float32)

        # Apply action clipping if enabled
        if self._enable_action_clipping:
            action = np.clip(
                action,
                self._action_limits["min"],
                self._action_limits["max"]
            )

        # Store for next iteration
        self._last_action = action.copy()

        # Create and populate the setpoint message
        msg = VehicleThrustAccSetpoint()
        msg.timestamp = int(time.time() * 1e6)  # Convert to microseconds

        # Extract and scale action components
        thrust_raw = action[0]  # Normalized thrust [-1, 1]
        roll_rate_raw = action[1]  # Normalized roll rate [-1, 1]
        pitch_rate_raw = action[2]  # Normalized pitch rate [-1, 1]
        yaw_rate_raw = action[3]  # Normalized yaw rate [-1, 1]

        # Convert to actual control values
        thrust_acc = self._convert_thrust_to_acceleration(thrust_raw)
        roll_rate = roll_rate_raw * self._max_roll_pitch_rate
        pitch_rate = pitch_rate_raw * self._max_roll_pitch_rate
        yaw_rate = yaw_rate_raw * self._max_yaw_rate

        # Convert angular rates from FLU to FRD coordinate system
        rate_flu = np.array([roll_rate, pitch_rate, yaw_rate])
        rate_frd = frd_flu_rotate(rate_flu)

        # Populate message fields
        msg.rates_sp[0] = rate_frd[0]  # Roll rate (FRD)
        msg.rates_sp[1] = rate_frd[1]  # Pitch rate (FRD)
        msg.rates_sp[2] = rate_frd[2]  # Yaw rate (FRD)
        msg.thrust_acc_sp = thrust_acc  # Thrust acceleration (positive up)

        return msg

    def _convert_thrust_to_acceleration(self, thrust_raw: float) -> float:
        """
        Convert normalized thrust to acceleration.

        Args:
            thrust_raw: Normalized thrust value [-1, 1]

        Returns:
            Thrust acceleration in m/s^2 (positive up)
        """
        if self._acc_fixed:
            # Use fixed acceleration for debugging
            return self._thrust_acc_base
        else:
            # Convert normalized thrust to acceleration
            # thrust_raw=0 -> base_thrust, thrust_raw=1 -> 2*base_thrust
            return thrust_raw * self._thrust_acc_base + self._thrust_acc_base

    def get_action_limits(self) -> dict:
        """
        Get the current action limits.

        Returns:
            Dictionary containing action limit configuration
        """
        return {
            "min": self._action_limits["min"],
            "max": self._action_limits["max"],
            "thrust_acc_base": self._thrust_acc_base,
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
        # Apply clipping if needed
        if self._enable_action_clipping:
            action = np.clip(
                raw_action,
                self._action_limits["min"],
                self._action_limits["max"]
            )
        else:
            action = raw_action.astype(np.float32)

        # Extract components
        thrust_raw = action[0]
        roll_rate_raw = action[1]
        pitch_rate_raw = action[2]
        yaw_rate_raw = action[3]

        # Convert to actual values
        thrust_acc = self._convert_thrust_to_acceleration(thrust_raw)
        roll_rate = roll_rate_raw * self._max_roll_pitch_rate
        pitch_rate = pitch_rate_raw * self._max_roll_pitch_rate
        yaw_rate = yaw_rate_raw * self._max_yaw_rate

        return {
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

        print(f"{prefix}🎮 控制指令 #{self._control_command_count} (4维):")
        print(f"{prefix}  ⬆️  推力加速度:     {action_display_dict['thrust_acc']:.3f} m/s² (原始: {action_display_dict['thrust_raw']:.3f})")
        print(f"{prefix}  🔄 横滚角速度:     {action_display_dict['roll_rate']:.3f} rad/s (原始: {action_display_dict['roll_rate_raw']:.3f})")
        print(f"{prefix}  🔄 俯仰角速度:     {action_display_dict['pitch_rate']:.3f} rad/s (原始: {action_display_dict['pitch_rate_raw']:.3f})")
        print(f"{prefix}  🔄 偏航角速度:     {action_display_dict['yaw_rate']:.3f} rad/s (原始: {action_display_dict['yaw_rate_raw']:.3f})")

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

        # Check for extreme values (after clipping)
        if self._enable_action_clipping:
            clipped_action = np.clip(
                raw_action,
                self._action_limits["min"],
                self._action_limits["max"]
            )
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
            "thrust_acc_base": self._thrust_acc_base,
            "max_roll_pitch_rate": self._max_roll_pitch_rate,
            "max_yaw_rate": self._max_yaw_rate,
            "acc_fixed": self._acc_fixed,
            "action_clipping_enabled": self._enable_action_clipping,
            "action_limits": self._action_limits,
            "last_action": self._last_action.tolist(),
        }

    def reset(self):
        """Reset processor state for fresh start."""
        self._last_action = np.zeros(4, dtype=np.float32)
        self._control_command_count = 0