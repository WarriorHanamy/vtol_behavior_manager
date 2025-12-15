#!/usr/bin/env python3
"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Observation Processor Component

Transforms VehicleOdometry messages into neural network observation format.
Handles coordinate transformations, observation construction, and input validation.
"""

from __future__ import annotations

import math
import time
from typing import Optional, Tuple

import numpy as np
import rclpy.node
from px4_msgs.msg import VehicleOdometry

from .math_utils import (
    frd_flu_rotate,
    quat_pas_rot,
    quat_right_multiply_flu_frd,
)


class ObservationProcessor:
    """
    Component responsible for processing VehicleOdometry messages into
    neural network observation format.
    """

    def __init__(
        self,
        target_position: np.ndarray,
        target_yaw: float,
        node_logger = None,
        enable_input_saturation: bool = True,
        saturation_limits: Optional[dict] = None,
        print_observations: bool = False,
    ):
        """
        Initialize the observation processor.

        Args:
            target_position: Target position in NED coordinates [x, y, z]
            target_yaw: Target yaw angle in radians
            node_logger: ROS2 node logger for debugging
            enable_input_saturation: Whether to apply input saturation limits
            saturation_limits: Dictionary containing saturation limit values
            print_observations: Whether to print detailed observation information
        """
        self._target_position = target_position.astype(np.float32)
        self._target_yaw = float(target_yaw)
        self._logger = node_logger
        self._enable_input_saturation = enable_input_saturation
        self._print_observations = print_observations

        # Default saturation limits
        if saturation_limits is None:
            saturation_limits = {
                "target_position": [-5.0, 5.0]
            }
        self._saturation_limits = saturation_limits

        # Timing statistics
        self._last_odom_receive_time = 0.0
        self._last_odom_sample_time = 0.0
        self._first_odom_received = False

        # Interval statistics for monitoring
        self._receive_interval_samples = []
        self._sample_interval_samples = []
        self._last_interval_report_time = 0.0
        self._interval_report_period = 5.0

        # Observation count for logging
        self._observation_count = 0

    def process_vehicle_odometry(self, msg: VehicleOdometry) -> Tuple[Optional[np.ndarray], bool]:
        """
        Process VehicleOdometry message into observation vector.

        Args:
            msg: VehicleOdometry ROS2 message

        Returns:
            Tuple of (observation_array, is_first_frame)
            observation_array: Processed observation or None if invalid
            is_first_frame: Whether this is the first odometry message received
        """
        # Check data timing and validity
        current_receive_time = time.time() * 1e6  # Convert to microseconds
        current_sample_time = msg.timestamp_sample

        # Handle first frame
        if not self._first_odom_received:
            self._first_odom_received = True
            self._last_odom_receive_time = current_receive_time
            self._last_odom_sample_time = current_sample_time
            self._last_interval_report_time = time.time()
            if self._logger:
                self._logger.info("✅ 收到第一帧里程计数据")

            # Process the first observation
            observation = self._extract_observation_from_message(msg)
            return observation, True

        # Calculate intervals for monitoring
        receive_interval = (current_receive_time - self._last_odom_receive_time) / 1000.0  # ms
        sample_interval = (current_sample_time - self._last_odom_sample_time) / 1000.0  # ms

        # Check for timeout conditions
        timeout_ms = 50.0  # Default timeout
        if receive_interval > timeout_ms and self._logger:
            self._logger.error(
                f"⚠️ 里程计接收间隔: {receive_interval:.1f} ms，数据过时"
            )
        elif sample_interval > timeout_ms and self._logger:
            self._logger.error(
                f"⚠️ 里程计采样间隔: {sample_interval:.1f} ms，数据过时"
            )

        # Record valid intervals for statistics
        if receive_interval <= timeout_ms:
            self._receive_interval_samples.append(receive_interval)
            if len(self._receive_interval_samples) > 100:
                self._receive_interval_samples.pop(0)

        if sample_interval <= timeout_ms:
            self._sample_interval_samples.append(sample_interval)
            if len(self._sample_interval_samples) > 100:
                self._sample_interval_samples.pop(0)

        # Periodic statistics reporting
        current_time = time.time()
        if current_time - self._last_interval_report_time >= self._interval_report_period:
            self._report_interval_statistics()

        # Update timing
        self._last_odom_receive_time = current_receive_time
        self._last_odom_sample_time = current_sample_time

        # Process observation
        observation = self._extract_observation_from_message(msg)
        return observation, False

    def _extract_observation_from_message(self, msg: VehicleOdometry) -> Optional[np.ndarray]:
        """
        Extract observation vector from VehicleOdometry message.

        Args:
            msg: VehicleOdometry message

        Returns:
            20-dimensional observation array or None if invalid data
        """
        # Validate message data
        if msg.timestamp_sample == 0 or np.allclose(msg.position, [0.0, 0.0, 0.0]):
            if self._logger:
                self._logger.warn("无效的里程计数据")
            return None

        # Extract position and velocity
        pos = np.array(msg.position, dtype=np.float32)  # NED coordinates [x, y, z]
        vel = np.array(msg.velocity, dtype=np.float32)  # Reference frame [vx, vy, vz]
        ang_vel_b_frd = np.array(msg.angular_velocity, dtype=np.float32)  # Body frame FRD
        quat_frd = np.array(msg.q, dtype=np.float32)  # [w, x, y, z] Hamilton convention

        # Transform to FLU coordinate system
        quat_flu = quat_right_multiply_flu_frd(quat_frd)

        # Calculate gravity direction and transform velocities
        gra_dir_w = np.array([0.0, 0.0, 1.0])  # Up direction in NED
        lin_vel_b_flu = quat_pas_rot(quat_flu, vel)
        ang_vel_b_flu = frd_flu_rotate(ang_vel_b_frd)
        gra_dir_b_flu = quat_pas_rot(quat_flu, gra_dir_w)

        # Calculate target position in body frame
        target_pos_w = self._target_position
        to_target = target_pos_w - pos
        to_target_pos_b_flu = quat_pas_rot(quat_flu, to_target)
        to_target_pos_b_flu[2] = 0.0  # Ignore vertical error

        # Calculate yaw directions
        current_yaw_dir = np.array([math.cos(0.0), math.sin(0.0)])  # Current yaw (simplified)
        target_yaw_dir = np.array([math.cos(self._target_yaw), math.sin(self._target_yaw)])

        # Assemble observation vector (20 dimensions as per config)
        observation = np.concatenate(
            [
                lin_vel_b_flu,           # 3D: Body linear velocity [vx, vy, vz]
                ang_vel_b_flu,           # 3D: Body angular velocity [wx, wy, wz]
                to_target_pos_b_flu,     # 3D: Target position in body frame [dx, dy, dz]
                gra_dir_b_flu,           # 3D: Gravity projection in body [gx, gy, gz]
                current_yaw_dir,         # 2D: Current yaw direction [cos(yaw), sin(yaw)]
                target_yaw_dir,          # 2D: Target yaw direction [cos(target_yaw), sin(target_yaw)]
                # Note: last_action (4D) will be added by the pipeline
            ],
            dtype=np.float32,
        )

        # Apply input saturation if enabled
        if self._enable_input_saturation:
            observation = self._apply_input_saturation(observation)

        return observation

    def _apply_input_saturation(self, observation: np.ndarray) -> np.ndarray:
        """
        Apply saturation limits to observation components.

        Args:
            observation: Input observation vector

        Returns:
            Saturated observation vector
        """
        # Saturate target position components (indices 6:8)
        target_pos_limits = self._saturation_limits.get("target_position", [-5.0, 5.0])
        observation[6:9] = np.clip(observation[6:9], target_pos_limits[0], target_pos_limits[1])

        return observation

    def print_observation(self, observation: np.ndarray, prefix: str = ""):
        """
        Print observation vector in human-readable format.

        Args:
            observation: Observation vector to print (with last action included)
            prefix: Optional prefix string for the output
        """
        if not self._print_observations or observation is None:
            return

        self._observation_count += 1

        # Ensure observation has expected length (20 dims: 16 obs + 4 last action)
        if len(observation) < 16:
            print(f"⚠️ 观测向量长度不足: {len(observation)} < 16")
            return

        # Extract observation components (based on 16-dim observation + 4-dim last action = 20 total)
        lin_vel_b = observation[0:3]  # 机体线速度
        ang_vel_b = observation[3:6]  # 机体角速度
        to_target_pos_b = observation[6:9]  # 目标位置(机体)
        gra_dir_b = observation[9:12]  # 机体重力投影
        current_yaw_dir = observation[12:14]  # 当前偏航方向
        target_yaw_dir = observation[14:16]  # 目标偏航方向

        # Include last action if available (indices 16:20)
        last_action = observation[16:20] if len(observation) >= 20 else None

        print(f"{prefix}📊 观测向量 #{self._observation_count}:")
        print(f"{prefix}  🎯 目标位置(机体): [{to_target_pos_b[0]:.3f}, {to_target_pos_b[1]:.3f}, {to_target_pos_b[2]:.3f}]")
        print(f"{prefix}  🚁 机体线速度:     [{lin_vel_b[0]:.3f}, {lin_vel_b[1]:.3f}, {lin_vel_b[2]:.3f}]")
        print(f"{prefix}  🔄 机体角速度:     [{ang_vel_b[0]:.3f}, {ang_vel_b[1]:.3f}, {ang_vel_b[2]:.3f}]")
        print(f"{prefix}  🌍 重力投影:       [{gra_dir_b[0]:.3f}, {gra_dir_b[1]:.3f}, {gra_dir_b[2]:.3f}]")
        print(f"{prefix}  🧭 当前偏航方向:   [{current_yaw_dir[0]:.3f}, {current_yaw_dir[1]:.3f}]")
        print(f"{prefix}  🎯 目标偏航方向:   [{target_yaw_dir[0]:.3f}, {target_yaw_dir[1]:.3f}]")

        if last_action is not None:
            print(f"{prefix}  ⏮️  上一帧动作:     [{last_action[0]:.3f}, {last_action[1]:.3f}, {last_action[2]:.3f}, {last_action[3]:.3f}]")

    def _report_interval_statistics(self):
        """Report timing statistics for monitoring."""
        if self._logger and (self._receive_interval_samples and self._sample_interval_samples):
            avg_receive = np.mean(self._receive_interval_samples)
            avg_sample = np.mean(self._sample_interval_samples)
            self._logger.info(
                f"📊 里程计统计 (最近{len(self._receive_interval_samples)}帧): "
                f"平均接收间隔={avg_receive:.1f}ms, 平均采样间隔={avg_sample:.1f}ms"
            )
        self._last_interval_report_time = time.time()

    def get_observation_info(self) -> dict:
        """
        Get observation processor information for debugging.

        Returns:
            Dictionary containing processor state and statistics
        """
        return {
            "target_position": self._target_position.tolist(),
            "target_yaw": self._target_yaw,
            "first_odometry_received": self._first_odom_received,
            "receive_interval_count": len(self._receive_interval_samples),
            "sample_interval_count": len(self._sample_interval_samples),
            "input_saturation_enabled": self._enable_input_saturation,
            "saturation_limits": self._saturation_limits,
        }

    def reset(self):
        """Reset processor state for fresh start."""
        self._first_odom_received = False
        self._last_odom_receive_time = 0.0
        self._last_odom_sample_time = 0.0
        self._receive_interval_samples.clear()
        self._sample_interval_samples.clear()
        self._last_interval_report_time = 0.0
        self._observation_count = 0