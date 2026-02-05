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
from geometry_msgs.msg import Vector3Stamped

from .math_utils import (
    frd_flu_rotate,
    quat_pas_rot,
    quat_right_multiply_flu_frd,
    quaternion_to_yaw,
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
        ros_node: Optional[rclpy.node.Node] = None,
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
            ros_node: ROS2 node for publishing observation data
        """
        self._target_position = target_position.astype(np.float32)
        self._target_yaw = float(target_yaw)
        self._logger = node_logger
        self._enable_input_saturation = enable_input_saturation
        self._print_observations = print_observations
        self._ros_node = ros_node

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

        # Create ROS2 publishers for observation details if node is provided
        self._linear_velocity_body_pub = None
        self._angular_velocity_body_pub = None
        self._gravity_direction_body_pub = None
        self._target_position_body_pub = None
        self._current_yaw_ned_pub = None
        self._target_yaw_ned_pub = None
        
        if self._ros_node is not None:
            # Linear velocity in body frame (机体系下的线速度)
            self._linear_velocity_body_pub = self._ros_node.create_publisher(
                Vector3Stamped,
                '/neural/linear_velocity_body',
                10
            )
            
            # Angular velocity in body frame (机体系下的角速度)
            self._angular_velocity_body_pub = self._ros_node.create_publisher(
                Vector3Stamped,
                '/neural/angular_velocity_body',
                10
            )
            
            # Gravity direction in body frame (机体系下的重力方向)
            self._gravity_direction_body_pub = self._ros_node.create_publisher(
                Vector3Stamped,
                '/neural/gravity_direction_body',
                10
            )
            
            # Target position in body frame (机体系下的目标位置)
            self._target_position_body_pub = self._ros_node.create_publisher(
                Vector3Stamped,
                '/neural/target_position_body',
                10
            )
            
            # Current yaw direction in NWU frame (NWU系下的当前偏航方向)
            self._current_yaw_nwu_pub = self._ros_node.create_publisher(
                Vector3Stamped,
                '/neural/current_yaw_nwu',
                10
            )
            
            # Target yaw direction in NWU frame (NWU系下的目标偏航方向)
            self._target_yaw_nwu_pub = self._ros_node.create_publisher(
                Vector3Stamped,
                '/neural/target_yaw_nwu',
                10
            )

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

        # Swap x and y components of gravity direction
        gra_dir_b_flu_raw = quat_pas_rot(quat_flu, gra_dir_w)
        gra_dir_b_flu = np.array([gra_dir_b_flu_raw[1], gra_dir_b_flu_raw[0], gra_dir_b_flu_raw[2]])

        # Calculate target position in body frame
        target_pos_w = self._target_position
        to_target = target_pos_w - pos
        to_target_pos_b_flu = quat_pas_rot(quat_flu, to_target)
        # to_target_pos_b_flu[2] = 0.0  # Ignore vertical error

        # Calculate yaw directions
        # Extract yaw angle from quaternion (NED-FRD frame)
        current_yaw_ned = quaternion_to_yaw(quat_frd)
        # Convert to NWU-FLU frame: yaw_nwu = -yaw_ned (coordinate system conversion)
        current_yaw_nwu = -current_yaw_ned
        target_yaw_nwu = -self._target_yaw  # Target yaw also needs conversion
        
        # Calculate yaw direction vectors in NWU frame
        current_yaw_dir_nwu = np.array([math.cos(current_yaw_nwu), math.sin(current_yaw_nwu)])
        target_yaw_dir_nwu = np.array([math.cos(target_yaw_nwu), math.sin(target_yaw_nwu)])

        # Assemble observation vector (16 dimensions, matching drone_pos_ctrl_env_cfg.py PolicyCfg)
        # Order MUST match training environment observation order exactly:
        # 1. lin_vel_b (3D) - body linear velocity
        # 2. proj_gravity_b (3D) - projected gravity in body frame
        # 3. ang_vel_b (3D) - body angular velocity
        # 4. target_pos_b (3D) - target position in body frame
        # 5. current_yaw_direction (2D) - current yaw direction in NWU frame
        # 6. target_yaw_w (2D) - target yaw direction in NWU frame
        # Total: 3+3+3+3+2+2 = 16 dimensions (last_action (4D) added by pipeline to make 20D)
        observation = np.concatenate(
            [
                lin_vel_b_flu,           # [0:3]   Body linear velocity [vx, vy, vz]
                gra_dir_b_flu,           # [3:6]   Gravity projection in body [gx, gy, gz]
                ang_vel_b_flu,           # [6:9]   Body angular velocity [wx, wy, wz]
                to_target_pos_b_flu,     # [9:12]  Target position in body frame [dx, dy, dz]
                current_yaw_dir_nwu,     # [12:14] Current yaw direction in NWU [cos(yaw), sin(yaw)]
                target_yaw_dir_nwu,      # [14:16] Target yaw direction in NWU [cos(target_yaw), sin(target_yaw)]
                # Note: last_action (4D) will be added by the pipeline at [16:20]
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
        # Saturate target position components (indices 9:12 in current order)
        target_pos_limits = self._saturation_limits.get("target_position", [-5.0, 5.0])
        observation[9:12] = np.clip(observation[9:12], target_pos_limits[0], target_pos_limits[1])

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

        # Extract observation components (order matching drone_pos_ctrl_env_cfg.py):
        # lin_vel_b(3), proj_gravity_b(3), ang_vel_b(3), target_pos_b(3), current_yaw(2), target_yaw(2)
        lin_vel_b = observation[0:3]          # 机体线速度
        gra_dir_b = observation[3:6]          # 机体重力投影
        ang_vel_b = observation[6:9]          # 机体角速度
        to_target_pos_b = observation[9:12]   # 目标位置(机体)
        current_yaw_dir = observation[12:14]  # 当前偏航方向
        target_yaw_dir = observation[14:16]   # 目标偏航方向

        # Include last action if available (indices 16:20)
        last_action = observation[16:20] if len(observation) >= 20 else None

        print(f"{prefix}📊 观测向量 #{self._observation_count}:")
        print(f"{prefix}  🚁 机体线速度:     [{lin_vel_b[0]:.3f}, {lin_vel_b[1]:.3f}, {lin_vel_b[2]:.3f}]")
        print(f"{prefix}  🌍 重力投影:       [{gra_dir_b[0]:.3f}, {gra_dir_b[1]:.3f}, {gra_dir_b[2]:.3f}]")
        print(f"{prefix}  🔄 机体角速度:     [{ang_vel_b[0]:.3f}, {ang_vel_b[1]:.3f}, {ang_vel_b[2]:.3f}]")
        print(f"{prefix}  🎯 目标位置(机体): [{to_target_pos_b[0]:.3f}, {to_target_pos_b[1]:.3f}, {to_target_pos_b[2]:.3f}]")
        print(f"{prefix}  🧭 当前偏航方向:   [{current_yaw_dir[0]:.3f}, {current_yaw_dir[1]:.3f}]")
        print(f"{prefix}  🎯 目标偏航方向:   [{target_yaw_dir[0]:.3f}, {target_yaw_dir[1]:.3f}]")

        if last_action is not None:
            print(f"{prefix}  ⏮️  上一帧动作:     [{last_action[0]:.3f}, {last_action[1]:.3f}, {last_action[2]:.3f}, {last_action[3]:.3f}]")

        # Publish observation details via ROS2 topic
        self._publish_observation_details(
            lin_vel_b, gra_dir_b, ang_vel_b, to_target_pos_b,
            current_yaw_dir, target_yaw_dir, last_action
        )

    def _publish_observation_details(
        self,
        lin_vel_b: np.ndarray,
        gra_dir_b: np.ndarray,
        ang_vel_b: np.ndarray,
        to_target_pos_b: np.ndarray,
        current_yaw_dir: np.ndarray,
        target_yaw_dir: np.ndarray,
        last_action: Optional[np.ndarray] = None,
    ):
        """
        Publish observation details to separate ROS2 topics.

        Args:
            lin_vel_b: Body linear velocity [3D]
            gra_dir_b: Gravity projection in body frame [3D]
            ang_vel_b: Body angular velocity [3D]
            to_target_pos_b: Target position in body frame [3D]
            current_yaw_dir: Current yaw direction [2D]
            target_yaw_dir: Target yaw direction [2D]
            last_action: Last action [4D], optional
        """
        if self._ros_node is None:
            return

        current_time = self._ros_node.get_clock().now().to_msg()

        # 1. Publish linear velocity in body frame
        if self._linear_velocity_body_pub is not None:
            vel_msg = Vector3Stamped()
            vel_msg.header.stamp = current_time
            vel_msg.header.frame_id = "body_flu"
            vel_msg.vector.x = float(lin_vel_b[0])
            vel_msg.vector.y = float(lin_vel_b[1])
            vel_msg.vector.z = float(lin_vel_b[2])
            self._linear_velocity_body_pub.publish(vel_msg)

        # 2. Publish angular velocity in body frame
        if self._angular_velocity_body_pub is not None:
            ang_vel_msg = Vector3Stamped()
            ang_vel_msg.header.stamp = current_time
            ang_vel_msg.header.frame_id = "body_flu"
            ang_vel_msg.vector.x = float(ang_vel_b[0])
            ang_vel_msg.vector.y = float(ang_vel_b[1])
            ang_vel_msg.vector.z = float(ang_vel_b[2])
            self._angular_velocity_body_pub.publish(ang_vel_msg)

        # 3. Publish gravity direction in body frame
        if self._gravity_direction_body_pub is not None:
            grav_msg = Vector3Stamped()
            grav_msg.header.stamp = current_time
            grav_msg.header.frame_id = "body_flu"
            grav_msg.vector.x = float(gra_dir_b[0])
            grav_msg.vector.y = float(gra_dir_b[1])
            grav_msg.vector.z = float(gra_dir_b[2])
            self._gravity_direction_body_pub.publish(grav_msg)

        # 4. Publish target position in body frame
        if self._target_position_body_pub is not None:
            target_msg = Vector3Stamped()
            target_msg.header.stamp = current_time
            target_msg.header.frame_id = "body_flu"
            target_msg.vector.x = float(to_target_pos_b[0])
            target_msg.vector.y = float(to_target_pos_b[1])
            target_msg.vector.z = float(to_target_pos_b[2])
            self._target_position_body_pub.publish(target_msg)

        # 5. Publish current yaw direction in NED frame
        if self._current_yaw_nwu_pub is not None:
            current_yaw_msg = Vector3Stamped()
            current_yaw_msg.header.stamp = current_time
            current_yaw_msg.header.frame_id = "nwu"
            current_yaw_msg.vector.x = float(current_yaw_dir[0])  # cos(current_yaw)
            current_yaw_msg.vector.y = float(current_yaw_dir[1])  # sin(current_yaw)
            current_yaw_msg.vector.z = 0.0
            self._current_yaw_nwu_pub.publish(current_yaw_msg)

        # 6. Publish target yaw direction in NED frame
        if self._target_yaw_nwu_pub is not None:
            target_yaw_msg = Vector3Stamped()
            target_yaw_msg.header.stamp = current_time
            target_yaw_msg.header.frame_id = "nwu"
            target_yaw_msg.vector.x = float(target_yaw_dir[0])  # cos(target_yaw)
            target_yaw_msg.vector.y = float(target_yaw_dir[1])  # sin(target_yaw)
            target_yaw_msg.vector.z = 0.0
            self._target_yaw_nwu_pub.publish(target_yaw_msg)

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