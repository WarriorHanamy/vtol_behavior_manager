#!/usr/bin/env python3
"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Communicator Component

Manages all ROS2 publishers and subscribers for the neural control system.
Handles message routing, topic management, and callback coordination.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import numpy as np
import rclpy.node
from px4_msgs.msg import VehicleOdometry, VehicleThrustAccSetpoint
from rclpy.qos import qos_profile_sensor_data


class Communicator:
    """
    Component responsible for all ROS2 communication including
    publishers, subscribers, and topic management.
    """

    def __init__(
        self,
        node: rclpy.node.Node,
        odometry_topic: str = "/fmu/out/vehicle_odometry",
        setpoint_topic: str = "/neural/control",
    ):
        """
        Initialize the communicator component.

        Args:
            node: ROS2 node instance
            odometry_topic: Topic name for VehicleOdometry subscription
            setpoint_topic: Topic name for VehicleThrustAccSetpoint publication
        """
        self._node = node
        self._odometry_topic = odometry_topic
        self._setpoint_topic = setpoint_topic

        # Callback storage
        self._odometry_callback: Optional[Callable] = None

        # Publisher and subscriber storage
        self._odometry_subscriber = None
        self._setpoint_publisher = None

        # Communication statistics
        self._messages_received = 0
        self._messages_published = 0
        self._last_publish_time = 0.0
        self._last_receive_time = 0.0
        self._start_time = time.time()

    def initialize_publishers(self):
        """Initialize ROS2 publishers."""
        try:
            self._setpoint_publisher = self._node.create_publisher(
                VehicleThrustAccSetpoint,
                self._setpoint_topic,
                qos_profile=qos_profile_sensor_data,
            )
            if self._node.get_logger():
                self._node.get_logger().info(f"✅ 发布者已初始化: {self._setpoint_topic}")
            return True
        except Exception as e:
            if self._node.get_logger():
                self._node.get_logger().error(f"❌ 发布者初始化失败: {e}")
            return False

    def initialize_subscribers(self, odometry_callback: Callable) -> bool:
        """
        Initialize ROS2 subscribers.

        Args:
            odometry_callback: Callback function for VehicleOdometry messages

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Store callback reference
            self._odometry_callback = odometry_callback

            # Create odometry subscriber
            self._odometry_subscriber = self._node.create_subscription(
                VehicleOdometry,
                self._odometry_topic,
                self._odometry_callback,
                qos_profile_sensor_data,
            )

            if self._node.get_logger():
                self._node.get_logger().info(f"✅ 订阅者已初始化: {self._odometry_topic}")
            return True
        except Exception as e:
            if self._node.get_logger():
                self._node.get_logger().error(f"❌ 订阅者初始化失败: {e}")
            return False

    def publish_control_setpoint(self, setpoint_msg: VehicleThrustAccSetpoint) -> bool:
        """
        Publish control setpoint message.

        Args:
            setpoint_msg: VehicleThrustAccSetpoint message to publish

        Returns:
            True if publish successful, False otherwise
        """
        if self._setpoint_publisher is None:
            if self._node.get_logger():
                self._node.get_logger().error("发布者未初始化，无法发布控制指令")
            return False

        try:
            self._setpoint_publisher.publish(setpoint_msg)
            self._messages_published += 1
            self._last_publish_time = time.time()
            return True
        except Exception as e:
            if self._node.get_logger():
                self._node.get_logger().error(f"发布控制指令失败: {e}")
            return False

    def publish_control_setpoint_with_validation(
        self,
        setpoint_msg: VehicleThrustAccSetpoint,
        validate_timestamp: bool = True,
        max_message_age: float = 0.1
    ) -> bool:
        """
        Publish control setpoint with validation.

        Args:
            setpoint_msg: VehicleThrustAccSetpoint message to publish
            validate_timestamp: Whether to validate message timestamp
            max_message_age: Maximum age of message in seconds

        Returns:
            True if publish successful and validation passed, False otherwise
        """
        # Validate publisher
        if self._setpoint_publisher is None:
            if self._node.get_logger():
                self._node.get_logger().error("发布者未初始化，无法发布控制指令")
            return False

        # Validate message content
        if validate_timestamp:
            current_time = time.time()
            message_timestamp = setpoint_msg.timestamp / 1e6  # Convert from microseconds

            if current_time - message_timestamp > max_message_age:
                if self._node.get_logger():
                    self._node.get_logger().warning(
                        f"消息时间戳过旧: {current_time - message_timestamp:.3f}s > {max_message_age}s"
                    )
                return False

        # Validate thrust and rates
        if not np.isfinite(setpoint_msg.thrust_acc_sp):
            if self._node.get_logger():
                self._node.get_logger().warning("推力加速度值无效 (NaN/Inf)")
            return False

        for i, rate in enumerate(setpoint_msg.rates_sp):
            if not np.isfinite(rate):
                if self._node.get_logger():
                    self._node.get_logger().warning(f"角速度值[{i}]无效 (NaN/Inf)")
                return False

        # Publish the validated message
        return self.publish_control_setpoint(setpoint_msg)

    def get_communication_stats(self) -> dict:
        """
        Get communication statistics for monitoring.

        Returns:
            Dictionary containing communication statistics
        """
        current_time = time.time()
        uptime = current_time - self._start_time

        return {
            "uptime_seconds": uptime,
            "messages_received": self._messages_received,
            "messages_published": self._messages_published,
            "receive_rate": self._messages_received / uptime if uptime > 0 else 0.0,
            "publish_rate": self._messages_published / uptime if uptime > 0 else 0.0,
            "last_receive_time": self._last_receive_time,
            "last_publish_time": self._last_publish_time,
            "odometry_topic": self._odometry_topic,
            "setpoint_topic": self._setpoint_topic,
        }

    def reset_statistics(self):
        """Reset communication statistics."""
        self._messages_received = 0
        self._messages_published = 0
        self._last_publish_time = 0.0
        self._last_receive_time = 0.0
        self._start_time = time.time()

    def get_topic_info(self) -> dict:
        """
        Get topic configuration information.

        Returns:
            Dictionary containing topic configuration
        """
        return {
            "odometry_topic": self._odometry_topic,
            "setpoint_topic": self._setpoint_topic,
            "subscriber_active": self._odometry_subscriber is not None,
            "publisher_active": self._setpoint_publisher is not None,
        }

    def is_ready(self) -> bool:
        """
        Check if communicator is ready for operation.

        Returns:
            True if both publisher and subscriber are initialized, False otherwise
        """
        return (self._setpoint_publisher is not None and
                self._odometry_subscriber is not None and
                self._odometry_callback is not None)

    def shutdown(self):
        """Clean shutdown of communicators."""
        try:
            if self._odometry_subscriber is not None:
                self._node.destroy_subscription(self._odometry_subscriber)
                self._odometry_subscriber = None

            if self._setpoint_publisher is not None:
                self._node.destroy_publisher(self._setpoint_publisher)
                self._setpoint_publisher = None

            if self._node.get_logger():
                self._node.get_logger().info("🔄 通信组件已关闭")
        except Exception as e:
            if self._node.get_logger():
                self._node.get_logger().error(f"关闭通信组件时出错: {e}")

    def __del__(self):
        """Destructor to ensure proper cleanup."""
        self.shutdown()