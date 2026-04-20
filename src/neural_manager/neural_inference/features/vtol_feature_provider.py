"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

VTOL Feature Provider Module

This module provides platform-specific feature provider for VTOL vehicles,
implementing coordinate transformations and sensor data processing.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from rclpy.qos import qos_profile_sensor_data

from neural_manager.neural_inference.math_utils import (
  canonicalize_quat_w_positive,
  frd_flu_rotate,
  ned_enu_rotate,
  ned_quat_frd_to_enu_quat_flu,
  ned_to_frd_rotate,
)
from px4_msgs.msg import TrajectorySetpoint, VehicleOdometry

from .feature_provider_base import FeatureProviderBase
from .protocols import InferenceNodeProtocol


class VtolFeatureProvider(FeatureProviderBase):
  """Platform-specific VTOL feature provider.

  This provider implements feature computation for VTOL vehicles with
  coordinate transformations from PX4 NED frame to neural network FLU frame.

  Sensor Data Buffers:
  - _ned_position: Vehicle position in NED frame [N, E, D] (meters)
  - _ned_velocity: Vehicle velocity in NED frame [N, E, D] (m/s)
  - _ned_quat_frd: Vehicle orientation quaternion [w, x, y, z] (Hamilton)
  - _frd_ang_vel: Angular velocity in FRD frame [roll, pitch, yaw] (rad/s)
  - _ned_target_position: Target position in NED frame [N, E, D] (meters)
  - _last_action: Buffered action vector [thrust, roll_rate, pitch_rate, yaw_rate]

  Constants:
  - GRAVITY_ACCEL: Standard gravity acceleration in m/s^2
  """

  GRAVITY_ACCEL: float = 9.81

  def __init__(
    self,
    metadata_path: Path | str,
    node: InferenceNodeProtocol | None = None,
    odometry_topic: str | None = None,
    target_topic: str | None = None,
  ):
    """Initialize the VTOL feature provider.

    Args:
        metadata_path: Path to observation_metadata.yaml file
        node: Optional inference node for subscription and inference trigger
        odometry_topic: Optional ROS2 topic for vehicle odometry
        target_topic: Optional ROS2 topic for target setpoint

    """
    self._ned_position: np.ndarray = np.zeros(3, dtype=np.float32)
    self._ned_velocity: np.ndarray = np.zeros(3, dtype=np.float32)
    self._ned_quat_frd: np.ndarray = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    self._frd_ang_vel: np.ndarray = np.zeros(3, dtype=np.float32)
    self._ned_target_position: np.ndarray = np.zeros(3, dtype=np.float32)
    self._last_action: np.ndarray = np.zeros(4, dtype=np.float32)

    self._node: InferenceNodeProtocol | None = node
    self._odom_sub = None
    self._target_sub = None

    super().__init__(metadata_path)

    if node is not None:
      if odometry_topic:
        self._odom_sub = node.create_subscription(
          VehicleOdometry,
          odometry_topic,
          self._on_odometry,
          qos_profile_sensor_data,
        )
      if target_topic:
        self._target_sub = node.create_subscription(
          TrajectorySetpoint,
          target_topic,
          self._on_target,
          qos_profile_sensor_data,
        )

  def _on_odometry(self, msg: VehicleOdometry) -> None:
    """Handle odometry message and trigger inference.

    Args:
        msg: VehicleOdometry message from PX4

    """
    ned_position = np.array([msg.position[0], msg.position[1], msg.position[2]], dtype=np.float32)
    ned_velocity = np.array([msg.velocity[0], msg.velocity[1], msg.velocity[2]], dtype=np.float32)
    ned_quat_frd = np.array([msg.q[0], msg.q[1], msg.q[2], msg.q[3]], dtype=np.float32)
    frd_ang_vel = np.array(
      [msg.angular_velocity[0], msg.angular_velocity[1], msg.angular_velocity[2]],
      dtype=np.float32,
    )
    self.update_vehicle_odom(ned_position, ned_velocity, ned_quat_frd, frd_ang_vel)

    if self._node is not None:
      self._node.run_inference()

  def _on_target(self, msg: TrajectorySetpoint) -> None:
    """Handle target setpoint message.

    Args:
        msg: TrajectorySetpoint message containing target position

    """
    if not any(math.isnan(x) for x in msg.position):
      self._ned_target_position = np.array(msg.position, dtype=np.float32)

  def update_vehicle_odom(
    self,
    ned_position: np.ndarray,
    ned_velocity: np.ndarray,
    ned_quat_frd: np.ndarray,
    frd_ang_vel: np.ndarray,
  ) -> None:
    """Update vehicle odometry data.

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

  def update_target(self, ned_target_position: np.ndarray) -> None:
    """Update target position.

    Args:
        ned_target_position: Target position in NED frame [N, E, D] (meters)

    """
    self._ned_target_position = self._ensure_float32(ned_target_position)

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

    Computes: Project gravity vector [0, 0, 9.81] from world to body frame and normalize

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

    Computes: Transform linear velocity from NED world frame to FLU body frame

    Returns:
        3D numpy array in FLU frame

    """
    frd_velocity = ned_to_frd_rotate(self._ned_quat_frd, self._ned_velocity)
    flu_velocity = frd_flu_rotate(frd_velocity)
    return flu_velocity

  def get_flu_ang_vel(self) -> np.ndarray:
    """Get angular velocity in FLU body frame.

    Computes: Transform angular velocity from FRD to FLU

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

    Transforms quaternion from NED FRD frame to ENU FLU frame.

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
        Dictionary containing raw sensor data for logging:
        - ned_position: Position in NED frame
        - ned_velocity: Velocity in NED frame
        - ned_quat_frd: Orientation quaternion [w, x, y, z]
        - frd_ang_vel: Angular velocity in FRD frame
        - ned_target_position: Target position in NED frame
        - last_action: Last action vector

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
    """Ensure numpy array is float32 dtype.

    Args:
        arr: Input numpy array

    Returns:
        Array converted to float32 dtype

    """
    return arr.astype(np.float32)
