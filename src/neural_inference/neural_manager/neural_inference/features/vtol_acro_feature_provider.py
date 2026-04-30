"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

VTOL Acro Feature Provider Module

This module provides platform-specific feature provider for VTOL acro tasks,
implementing gate-relative observations from GoalAcro messages.

Note: ROS subscriptions are managed by NeuralControlNode, not by this class.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from goal_msgs.msg import GoalAcro
from neural_manager.neural_inference.math_utils import (
  frd_flu_rotate,
  ned_to_frd_rotate,
  quat_conjugate,
)

from .feature_provider_base import FeatureProviderBase


class VtolAcroFeatureProvider(FeatureProviderBase):
  """Feature provider for VTOL acro task with gate-relative observations.

  Sensor Data Buffers (updated externally by NeuralControlNode):
  - _ned_position: Vehicle position in NED frame [N, E, D] (meters)
  - _ned_velocity: Vehicle velocity in NED frame [N, E, D] (m/s)
  - _ned_quat_frd: Vehicle orientation quaternion [w, x, y, z] (Hamilton)
  - _frd_ang_vel: Angular velocity in FRD frame [roll, pitch, yaw] (rad/s)
  - _gate_center: Gate center in NED frame [N, E, D] (meters)
  - _semi_major: Gate semi-major axis [m]
  - _semi_short: Gate semi-minor axis [m]
  - _last_action: Buffered action vector [thrust, roll_rate, pitch_rate, yaw_rate]
  """

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
    self._gate_center: np.ndarray = np.zeros(3, dtype=np.float32)
    self._semi_major: float = 0.0
    self._semi_short: float = 0.0
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
    self._ned_position = ned_position.astype(np.float32)
    self._ned_velocity = ned_velocity.astype(np.float32)
    self._ned_quat_frd = ned_quat_frd.astype(np.float32)
    self._frd_ang_vel = frd_ang_vel.astype(np.float32)

  def get_goal_str(self) -> str:
    """Get human-readable goal string for logging."""
    g = self._gate_center
    return (
      f"gate_center=[{g[0]:.2f}, {g[1]:.2f}, {g[2]:.2f}] "
      f"semi_major={self._semi_major:.2f} semi_short={self._semi_short:.2f}"
    )

  def update_from_goal_acro(self, msg: GoalAcro) -> None:
    """Update target from GoalAcro sub-message (called by NeuralControlNode).

    Args:
        msg: GoalAcro message containing gate center and geometry

    """
    self._gate_center = np.array(msg.gate_center, dtype=np.float32)
    self._semi_major = float(msg.semi_major)
    self._semi_short = float(msg.semi_short)

  def update_last_action(self, action: np.ndarray) -> None:
    """Buffer the last action vector.

    Args:
        action: Action vector [thrust, roll_rate, pitch_rate, yaw_rate]

    """
    self._last_action = action.astype(np.float32)

  def get_gate_layout(self) -> np.ndarray:
    """Static gate geometry: (2,) [semi_major, semi_short].

    Returns:
        2D numpy array with gate semi-axes [m]

    """
    return np.array([self._semi_major, self._semi_short], dtype=np.float32)

  def get_gate_pose(self) -> np.ndarray:
    """Dynamic gate pose: (6,) [rel_pos_b(3), normal_b(3)].

    Returns:
        6D numpy array: [rel_pos_b_x, rel_pos_b_y, rel_pos_b_z,
                         normal_b_x, normal_b_y, normal_b_z]

    """
    rel_ned = self._gate_center - self._ned_position
    rel_frd = ned_to_frd_rotate(quat_conjugate(self._ned_quat_frd), rel_ned)
    rel_flu = frd_flu_rotate(rel_frd)

    normal_ned = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    normal_frd = ned_to_frd_rotate(quat_conjugate(self._ned_quat_frd), normal_ned)
    normal_flu = frd_flu_rotate(normal_frd)

    return np.concatenate([rel_flu, normal_flu]).astype(np.float32)

  def get_flu_vel(self) -> np.ndarray:
    """Get linear velocity in FLU body frame.

    Returns:
        3D numpy array in FLU frame

    """
    frd_velocity = ned_to_frd_rotate(quat_conjugate(self._ned_quat_frd), self._ned_velocity)
    flu_velocity = frd_flu_rotate(frd_velocity)
    return flu_velocity.astype(np.float32)

  def get_flu_ang_vel(self) -> np.ndarray:
    """Get angular velocity in FLU body frame.

    Returns:
        3D numpy array in FLU frame

    """
    flu_ang_vel = frd_flu_rotate(self._frd_ang_vel)
    return flu_ang_vel.astype(np.float32)

  def get_last_raw_action(self) -> np.ndarray:
    """Get the buffered last action vector.

    Returns:
        4D numpy array [thrust, roll_rate, pitch_rate, yaw_rate]

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
      "gate_center": self._gate_center.copy(),
      "semi_major": self._semi_major,
      "semi_short": self._semi_short,
      "last_action": self._last_action.copy(),
    }
