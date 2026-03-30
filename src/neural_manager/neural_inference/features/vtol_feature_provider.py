"""
Copyright (c) 2025, Differential Robotics
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

from px4_msgs.msg import TrajectorySetpoint, VehicleOdometry

from .feature_provider_base import FeatureProviderBase
from .protocols import InferenceNodeProtocol


class VtolFeatureProvider(FeatureProviderBase):
  """
  Platform-specific VTOL feature provider.

  This provider implements feature computation for VTOL vehicles with
  coordinate transformations from PX4 NED frame to neural network FLU frame.

  Sensor Data Buffers:
  - _position_ned: Vehicle position in NED frame [N, E, D] (meters)
  - _velocity_ned: Vehicle velocity in NED frame [N, E, D] (m/s)
  - _quat: Vehicle orientation quaternion [w, x, y, z] (Hamilton)
  - _ang_vel_frd: Angular velocity in FRD frame [roll, pitch, yaw] (rad/s)
  - _target_pos_ned: Target position in NED frame [N, E, D] (meters)
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
    """
    Initialize the VTOL feature provider.

    Args:
        metadata_path: Path to observation_metadata.yaml file
        node: Optional inference node for subscription and inference trigger
        odometry_topic: Optional ROS2 topic for vehicle odometry
        target_topic: Optional ROS2 topic for target setpoint
    """
    self._position_ned: np.ndarray = np.zeros(3, dtype=np.float32)
    self._velocity_ned: np.ndarray = np.zeros(3, dtype=np.float32)
    self._quat: np.ndarray = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    self._ang_vel_frd: np.ndarray = np.zeros(3, dtype=np.float32)
    self._target_pos_ned: np.ndarray = np.zeros(3, dtype=np.float32)
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
    """
    Handle odometry message and trigger inference.

    Args:
        msg: VehicleOdometry message from PX4
    """
    position = np.array([msg.position[0], msg.position[1], msg.position[2]], dtype=np.float32)
    velocity = np.array([msg.velocity[0], msg.velocity[1], msg.velocity[2]], dtype=np.float32)
    quat = np.array([msg.q[0], msg.q[1], msg.q[2], msg.q[3]], dtype=np.float32)
    ang_vel = np.array(
      [msg.angular_velocity[0], msg.angular_velocity[1], msg.angular_velocity[2]],
      dtype=np.float32,
    )
    self.update_vehicle_odom(position, velocity, quat, ang_vel)

    if self._node is not None:
      self._node.run_inference()

  def _on_target(self, msg: TrajectorySetpoint) -> None:
    """
    Handle target setpoint message.

    Args:
        msg: TrajectorySetpoint message containing target position
    """
    if not any(math.isnan(x) for x in msg.position):
      self._target_pos_ned = np.array(msg.position, dtype=np.float32)

  def update_vehicle_odom(
    self,
    position: np.ndarray,
    velocity: np.ndarray,
    quat: np.ndarray,
    ang_vel: np.ndarray,
  ) -> None:
    """
    Update vehicle odometry data.

    Args:
        position: Vehicle position in NED frame [N, E, D] (meters)
        velocity: Vehicle velocity in NED frame [N, E, D] (m/s)
        quat: Vehicle orientation quaternion [w, x, y, z] (Hamilton)
        ang_vel: Angular velocity in FRD frame [roll, pitch, yaw] (rad/s)
    """
    self._position_ned = self._ensure_float32(position)
    self._velocity_ned = self._ensure_float32(velocity)
    self._quat = self._ensure_float32(quat)
    self._ang_vel_frd = self._ensure_float32(ang_vel)

  def update_target(self, target_pos: np.ndarray) -> None:
    """
    Update target position.

    Args:
        target_pos: Target position in NED frame [N, E, D] (meters)
    """
    self._target_pos_ned = self._ensure_float32(target_pos)

  def update_last_action(self, action: np.ndarray) -> None:
    """
    Buffer the last action vector.

    Args:
        action: Action vector [thrust, roll_rate, pitch_rate, yaw_rate]
    """
    self._last_action = self._ensure_float32(action)

  def get_to_target_b(self) -> np.ndarray:
    """
    Get target error vector in FLU body frame.

    Computes: target_pos - vehicle_pos in FLU frame

    Returns:
        3D numpy array representing target error in FLU frame
    """
    error_ned = self._target_pos_ned - self._position_ned
    error_frd = self._ned_to_frd(self._quat, error_ned)
    error_flu = self._frd_to_flu(error_frd)
    return error_flu

  def get_grav_dir_b(self) -> np.ndarray:
    """
    Get gravity direction vector in FLU body frame.

    Computes: Project gravity vector [0, 0, 9.81] from world to body frame and normalize

    Returns:
        3D normalized numpy array in FLU frame
    """
    gravity_ned = np.array([0.0, 0.0, self.GRAVITY_ACCEL], dtype=np.float32)
    gravity_frd = self._ned_to_frd(self._quat, gravity_ned)
    gravity_flu = self._frd_to_flu(gravity_frd)
    norm = np.linalg.norm(gravity_flu)
    return gravity_flu / norm if norm > 0 else gravity_flu

  def get_lin_vel_b(self) -> np.ndarray:
    """
    Get linear velocity in FLU body frame.

    Computes: Transform linear velocity from NED world frame to FLU body frame

    Returns:
        3D numpy array in FLU frame
    """
    velocity_frd = self._ned_to_frd(self._quat, self._velocity_ned)
    velocity_flu = self._frd_to_flu(velocity_frd)
    return velocity_flu

  def get_ang_vel_b(self) -> np.ndarray:
    """
    Get angular velocity in FLU body frame.

    Computes: Transform angular velocity from FRD to FLU

    Returns:
        3D numpy array in FLU frame
    """
    ang_vel_flu = self._frd_to_flu(self._ang_vel_frd)
    return ang_vel_flu

  def get_last_action(self) -> np.ndarray:
    """
    Get the buffered last action vector.

    Returns:
        4D numpy array [thrust, roll_rate, pitch_rate, yaw_rate]
    """
    return self._last_action

  def get_to_target_b_flu(self) -> np.ndarray:
    """
    Get target error vector in FLU body frame.

    Computes: target_pos - vehicle_pos in FLU frame

    Returns:
        3D numpy array representing target error in FLU frame
    """
    error_ned = self._target_pos_ned - self._position_ned
    error_frd = self._ned_to_frd(self._quat, error_ned)
    error_flu = self._frd_to_flu(error_frd)
    return error_flu

  def get_enu_quat_flu(self) -> np.ndarray:
    """
    Get orientation quaternion in ENU FLU frame.

    Transforms quaternion from NED FRD frame to ENU FLU frame.

    Returns:
        4D numpy array [w, x, y, z] quaternion in ENU FLU frame
    """
    q_w, q_x, q_y, q_z = self._quat
    enu_quat = np.array([q_w, -q_y, q_x, -q_z], dtype=np.float32)
    return enu_quat

  def get_vel_b_flu(self) -> np.ndarray:
    """
    Get linear velocity in FLU body frame.

    Computes: Transform linear velocity from NED world frame to FLU body frame

    Returns:
        3D numpy array in FLU frame
    """
    velocity_frd = self._ned_to_frd(self._quat, self._velocity_ned)
    velocity_flu = self._frd_to_flu(velocity_frd)
    return velocity_flu

  def get_ang_vel_b_flu(self) -> np.ndarray:
    """
    Get angular velocity in FLU body frame.

    Computes: Transform angular velocity from FRD to FLU

    Returns:
        3D numpy array in FLU frame
    """
    ang_vel_flu = self._frd_to_flu(self._ang_vel_frd)
    return ang_vel_flu

  def get_last_raw_action(self) -> np.ndarray:
    """
    Get the buffered last raw action vector (semantic-agnostic).

    Returns:
        4D numpy array representing raw network output
    """
    return self._last_action

  def get_raw_input(self) -> dict:
    """
    Get raw sensor data before feature transformation.

    Returns:
        Dictionary containing raw sensor data for logging:
        - position_ned: Position in NED frame
        - velocity_ned: Velocity in NED frame
        - quat: Orientation quaternion [w, x, y, z]
        - ang_vel_frd: Angular velocity in FRD frame
        - target_pos_ned: Target position in NED frame
        - last_action: Last action vector
    """
    return {
      "position_ned": self._position_ned.copy(),
      "velocity_ned": self._velocity_ned.copy(),
      "quat": self._quat.copy(),
      "ang_vel_frd": self._ang_vel_frd.copy(),
      "target_pos_ned": self._target_pos_ned.copy(),
      "last_action": self._last_action.copy(),
    }

  def _ensure_float32(self, arr: np.ndarray) -> np.ndarray:
    """
    Ensure numpy array is float32 dtype.

    Args:
        arr: Input numpy array

    Returns:
        Array converted to float32 dtype
    """
    return arr.astype(np.float32)

  def _ned_to_frd(self, quat: np.ndarray, vec: np.ndarray) -> np.ndarray:
    """
    Transform a vector from NED frame to FRD body frame using quaternion.

    Uses active rotation: the vector is rotated, not the coordinate system.

    Args:
        quat: Quaternion [w, x, y, z] representing body orientation.
        vec: Vector in NED frame [vx, vy, vz].

    Returns:
        Vector in FRD body frame [vx, vy, vz].
    """
    w, u = quat[0], quat[1:4]
    uv = np.cross(u, vec)
    uuv = np.cross(u, uv)
    return vec + 2.0 * (w * uv + uuv)

  def _frd_to_flu(self, vec: np.ndarray) -> np.ndarray:
    """
    Transform a vector from FRD frame to FLU frame.

    FRD (Forward-Right-Down) and FLU (Forward-Left-Up) are both body frames
    but with different axis conventions.

    This transformation rotates the Y and Z axes:
    - X (Forward) stays the same
    - Y: Right -> Left (negated)
    - Z: Down -> Up (negated)

    Args:
        vec: Vector in FRD frame [vx, vy, vz].

    Returns:
        Vector in FLU frame [vx, vy, vz].
    """
    result = vec.copy()
    result[1] = -result[1]
    result[2] = -result[2]
    return result
