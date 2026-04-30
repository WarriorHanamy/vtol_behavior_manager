"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

VTOL Hover Feature Provider Module

This module provides platform-specific feature provider for VTOL hover task,
implementing coordinate transformations and sensor data processing.

Note: ROS subscriptions are managed by NeuralControlNode, not by this class.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from goal_msgs.msg import GoalHover
from neural_manager.neural_inference.math_utils import (
  canonicalize_quat_w_positive,
  frd_flu_rotate,
  ned_enu_rotate,
  ned_quat_frd_to_enu_quat_flu,
  ned_to_frd_rotate,
)

from .feature_provider_base import FeatureProviderBase


class VtolHoverFeatureProvider(FeatureProviderBase):
  """Platform-specific VTOL hover feature provider.

  Feature computation for VTOL hover task with coordinate transformations
  from PX4 NED frame to neural network FLU frame.

  Sensor Data Buffers (updated externally by NeuralControlNode):
  - _ned_position: Vehicle position in NED frame [N, E, D] (meters)
  - _ned_velocity: Vehicle velocity in NED frame [N, E, D] (m/s)
  - _ned_quat_frd: Vehicle orientation quaternion [w, x, y, z] (Hamilton)
  - _frd_ang_vel: Angular velocity in FRD frame [roll, pitch, yaw] (rad/s)
  - _ned_target_position: Target position in NED frame [N, E, D] (meters)
  - _last_action: Buffered action vector [thrust, roll_rate, pitch_rate, yaw_rate]
  """

  GRAVITY_ACCEL: float = 9.81

  def __init__(
    self,
    metadata_path: Path | str,
    node=None,
    odometry_topic: str | None = None,
    target_topic: str | None = None,
    odom_rate: float = 100.0,
    inference_rate: float = 50.0,
  ):
    self._ned_position: np.ndarray = np.zeros(3, dtype=np.float32)
    self._ned_velocity: np.ndarray = np.zeros(3, dtype=np.float32)
    self._ned_quat_frd: np.ndarray = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    self._frd_ang_vel: np.ndarray = np.zeros(3, dtype=np.float32)
    self._ned_target_position: np.ndarray = np.zeros(3, dtype=np.float32)
    self._last_action: np.ndarray = np.zeros(4, dtype=np.float32)

    super().__init__(metadata_path)

  def update_vehicle_odom(
    self,
    ned_position: np.ndarray,
    ned_velocity: np.ndarray,
    ned_quat_frd: np.ndarray,
    frd_ang_vel: np.ndarray,
  ) -> None:
    """Update vehicle odometry data (called by NeuralControlNode).

    Args:
        ned_position: Vehicle position in NED frame [N, E, D] (meters)
        ned_velocity: Vehicle velocity in NED frame [N, E, D] (m/s)
        ned_quat_frd: Vehicle orientation quaternion [w, x, y, z] (Hamilton)
        frd_ang_vel: Angular velocity in FRD frame [roll, pitch, yaw] (rad/s)

    """
    self._ned_position = self._ensure_float32(ned_position)
    self._ned_velocity = self._ensure_float32(ned_velocity)
    self._ned_quat_frd = self._ensure_float32(ned_quat_frd)
    self._frd_ang_vel = self._ensure_float32(frd_ang_vel)

  def get_goal_str(self) -> str:
    """Get human-readable goal string for logging."""
    p = self._ned_target_position
    return f"ned_target=[{p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f}]"

  def update_from_goal_hover(self, msg: GoalHover) -> None:
    """Update target from GoalHover sub-message (called by NeuralControlNode).

    Args:
        msg: GoalHover message containing target position

    """
    import math

    if not any(math.isnan(x) for x in msg.position):
      self._ned_target_position = np.array(msg.position, dtype=np.float32)

  def update_last_action(self, action: np.ndarray) -> None:
    """Buffer the last action vector.

    Args:
        action: Action vector [thrust, roll_rate, pitch_rate, yaw_rate]

    """
    self._last_action = self._ensure_float32(action)

  def get_flu_to_target(self) -> np.ndarray:
    """Get target error vector in FLU body frame.

    Computes: target_position - vehicle_position in FLU frame

    Returns:
        3D numpy array representing target error in FLU frame

    """
    ned_error = self._ned_target_position - self._ned_position
    frd_error = ned_to_frd_rotate(self._ned_quat_frd, ned_error)
    flu_error = frd_flu_rotate(frd_error)
    return flu_error

  def get_enu_to_target(self) -> np.ndarray:
    """Get target error vector in ENU world frame.

    Computes: target_position - vehicle_position in ENU frame

    Returns:
        3D numpy array representing target error in ENU frame [e, n, -d]

    """
    ned_error = self._ned_target_position - self._ned_position
    enu_error = ned_enu_rotate(ned_error)
    return enu_error

  def get_flu_grav_dir(self) -> np.ndarray:
    """Get gravity direction vector in FLU body frame.

    Returns:
        3D normalized numpy array in FLU frame

    """
    ned_gravity = np.array([0.0, 0.0, self.GRAVITY_ACCEL], dtype=np.float32)
    frd_gravity = ned_to_frd_rotate(self._ned_quat_frd, ned_gravity)
    flu_gravity = frd_flu_rotate(frd_gravity)
    norm = np.linalg.norm(flu_gravity)
    return flu_gravity / norm if norm > 0 else flu_gravity

  def get_flu_vel(self) -> np.ndarray:
    """Get linear velocity in FLU body frame.

    Returns:
        3D numpy array in FLU frame

    """
    frd_velocity = ned_to_frd_rotate(self._ned_quat_frd, self._ned_velocity)
    flu_velocity = frd_flu_rotate(frd_velocity)
    return flu_velocity

  def get_flu_ang_vel(self) -> np.ndarray:
    """Get angular velocity in FLU body frame.

    Returns:
        3D numpy array in FLU frame

    """
    flu_ang_vel = frd_flu_rotate(self._frd_ang_vel)
    return flu_ang_vel

  def get_last_action(self) -> np.ndarray:
    """Get the buffered last action vector.

    Returns:
        4D numpy array [thrust, roll_rate, pitch_rate, yaw_rate]

    """
    return self._last_action

  def get_enu_quat_flu(self) -> np.ndarray:
    """Get orientation quaternion in ENU FLU frame.

    Returns:
        4D numpy array [w, x, y, z] quaternion in ENU FLU frame

    """
    enu_quat_flu = ned_quat_frd_to_enu_quat_flu(self._ned_quat_frd).astype(np.float32)
    return canonicalize_quat_w_positive(enu_quat_flu)

  def get_last_raw_action(self) -> np.ndarray:
    """Get the buffered last raw action vector (semantic-agnostic).

    Returns:
        4D numpy array representing raw network output

    """
    return self._last_action

  def get_raw_input(self) -> dict:
    """Get raw sensor data before feature transformation.

    Returns:
        Dictionary containing raw sensor data for logging

    """
    return {
      "ned_position": self._ned_position.copy(),
      "ned_velocity": self._ned_velocity.copy(),
      "ned_quat_frd": self._ned_quat_frd.copy(),
      "frd_ang_vel": self._frd_ang_vel.copy(),
      "ned_target_position": self._ned_target_position.copy(),
      "last_action": self._last_action.copy(),
    }

  def _ensure_float32(self, arr: np.ndarray) -> np.ndarray:
    """Ensure numpy array is float32 dtype."""
    return arr.astype(np.float32)
