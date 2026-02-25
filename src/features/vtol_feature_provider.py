"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

VTOL Feature Provider Module

This module provides platform-specific feature provider for VTOL vehicles,
implementing coordinate transformations and sensor data processing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from .feature_provider_base import FeatureProviderBase


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

    def __init__(self, metadata_path: Path | str):
        """
        Initialize the VTOL feature provider.

        Args:
            metadata_path: Path to observation_metadata.yaml file
        """
        # Initialize sensor data buffers before calling super().__init__()
        # This is necessary because super().__init__() calls _validate_implementations()
        # which in turn calls the get_{feature_name}() methods that depend on these attributes
        self._position_ned: Optional[np.ndarray] = None
        self._velocity_ned: Optional[np.ndarray] = None
        self._quat: Optional[np.ndarray] = None
        self._ang_vel_frd: Optional[np.ndarray] = None
        self._target_pos_ned: Optional[np.ndarray] = None
        self._last_action: Optional[np.ndarray] = None

        # Now call parent class __init__ which will validate implementations
        super().__init__(metadata_path)

    # =========================================================================
    # Sensor Update Methods
    # =========================================================================

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

    def update_imu(self, linear_accel: np.ndarray, ang_vel: np.ndarray) -> None:
        """
        Update IMU data.

        Args:
            linear_accel: Linear acceleration (m/s^2)
            ang_vel: Angular velocity in FRD frame [roll, pitch, yaw] (rad/s)
        """
        # Store angular velocity for get_ang_vel_b()
        self._ang_vel_frd = ang_vel.astype(np.float32)

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

    # =========================================================================
    # Feature Get Methods
    # =========================================================================

    def get_to_target_b(self) -> Optional[np.ndarray]:
        """
        Get target error vector in FLU body frame.

        Computes: target_pos - vehicle_pos in FLU frame

        Returns:
            3D numpy array representing target error in FLU frame, or None if data unavailable
        """
        if (
            self._position_ned is None
            or self._target_pos_ned is None
            or self._quat is None
        ):
            return None

        # Compute target error in NED frame
        error_ned = self._target_pos_ned - self._position_ned

        # Transform from NED to FRD using quaternion
        error_frd = self._ned_to_frd(self._quat, error_ned)

        # Transform from FRD to FLU
        error_flu = self._frd_to_flu(error_frd)

        return error_flu

    def get_grav_dir_b(self) -> Optional[np.ndarray]:
        """
        Get gravity direction vector in FLU body frame.

        Computes: Project gravity vector [0, 0, 9.81] from world to body frame and normalize

        Returns:
            3D normalized numpy array in FLU frame, or None if data unavailable
        """
        if self._quat is None:
            return None

        # Gravity vector in world NED frame (pointing down)
        gravity_ned = np.array([0.0, 0.0, self.GRAVITY_ACCEL], dtype=np.float32)

        # Transform from NED to FRD using quaternion
        gravity_frd = self._ned_to_frd(self._quat, gravity_ned)

        # Transform from FRD to FLU
        gravity_flu = self._frd_to_flu(gravity_frd)

        # Normalize
        gravity_flu_norm = gravity_flu / np.linalg.norm(gravity_flu)

        return gravity_flu_norm

    def get_ang_vel_b(self) -> Optional[np.ndarray]:
        """
        Get angular velocity in FLU body frame.

        Computes: Transform angular velocity from FRD to FLU

        Returns:
            3D numpy array in FLU frame, or None if data unavailable
        """
        if self._ang_vel_frd is None:
            return None

        # Transform from FRD to FLU
        ang_vel_flu = self._frd_to_flu(self._ang_vel_frd)

        return ang_vel_flu

    def get_last_action(self) -> Optional[np.ndarray]:
        """
        Get the buffered last action vector.

        Returns:
            4D numpy array [thrust, roll_rate, pitch_rate, yaw_rate], or None if not buffered
        """
        if self._last_action is None:
            return None

        return self._last_action

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _ensure_float32(self, arr: np.ndarray) -> np.ndarray:
        """
        Ensure numpy array is float32 dtype.

        Args:
            arr: Input numpy array

        Returns:
            Array converted to float32 dtype
        """
        return arr.astype(np.float32)

    # =========================================================================
    # Coordinate Transformation Helpers
    # =========================================================================

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
        # Active rotation using quaternion
        # v' = q * v * q_conj
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
        # Negate Y and Z components
        result = vec.copy()
        result[1] = -result[1]  # Right -> Left
        result[2] = -result[2]  # Down -> Up
        return result
