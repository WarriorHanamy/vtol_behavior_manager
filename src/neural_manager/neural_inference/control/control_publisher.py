"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Control Publisher Component

Publishes neural network control outputs to ROS2 topics for PX4 integration.
Fixed message format on /neural/control topic:
- acc_p_z: float [m/s²] - Z-axis acceleration
- bodyrate: np.ndarray [wx, wy, wz] [rad/s] - 3D angular velocity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

# Handle ROS2 imports gracefully
ROS2_AVAILABLE = False
VehicleAccRatesSetpoint = None
rclpy_node = None

try:
  import rclpy.node as rclpy_node

  from px4_msgs.msg import VehicleAccRatesSetpoint

  ROS2_AVAILABLE = True
except ImportError:
  pass


@dataclass
class NeuralControlMessage:
  """
  Simple mock message class for neural control when ROS2 is not available.

  Attributes:
      timestamp: Message timestamp in microseconds
      acc_p_z: Z-axis acceleration in m/s²
      bodyrate: 3D angular velocity [wx, wy, wz] in rad/s
  """

  timestamp: int = 0
  acc_p_z: float = 0.0
  bodyrate: np.ndarray = None

  def __post_init__(self):
    if self.bodyrate is None:
      self.bodyrate = np.zeros(3, dtype=np.float32)


class ControlPublisher:
  """
  Publisher for neural network control outputs.

  Publishes control messages to /neural/control topic with fixed format:
  - acc_p_z: Z-axis acceleration [m/s²]
  - bodyrate: Angular velocity [wx, wy, wz] [rad/s]

  If ROS2 is available and node is provided, uses px4_msgs.VehicleAccRatesSetpoint.
  Otherwise, creates a simple mock message for testing.
  """

  TOPIC_NAME = "/neural/control"

  def __init__(self, node: Any | None = None):
    """
    Initialize the control publisher.

    Args:
        node: Optional ROS2 node for creating publishers.
              If None, publisher will not be initialized until initialize() is called.
    """
    self._node = node
    self._publisher = None
    self._is_initialized = False
    self._publish_count = 0

  def initialize(self) -> bool:
    """
    Initialize the publisher if a ROS2 node was provided.

    Returns:
        True if publisher was successfully initialized, False otherwise.
    """
    if self._is_initialized:
      return True

    if self._node is None:
      return False

    if not ROS2_AVAILABLE:
      return False

    try:
      self._publisher = self._node.create_publisher(
        VehicleAccRatesSetpoint,
        self.TOPIC_NAME,
        10,
      )
      self._is_initialized = True

      logger = self._node.get_logger()
      logger.info(f"📡 ControlPublisher initialized on topic: {self.TOPIC_NAME}")
      return True
    except Exception as e:
      if self._node is not None:
        logger = self._node.get_logger()
        logger.warning(f"Failed to create publisher: {e}")
      return False

  def create_control_message(self, acc_p_z: float, bodyrate: np.ndarray, timestamp: int) -> Any:
    """
    Create a control message with the given parameters.

    Args:
        acc_p_z: Z-axis acceleration in m/s²
        bodyrate: 3D angular velocity [wx, wy, wz] in rad/s
        timestamp: Message timestamp in microseconds

    Returns:
        VehicleAccRatesSetpoint if ROS2 available, otherwise NeuralControlMessage
    """
    # Validate inputs
    if not np.isfinite(acc_p_z):
      acc_p_z = 0.0

    bodyrate = np.asarray(bodyrate, dtype=np.float32)
    if bodyrate.shape != (3,):
      bodyrate = np.zeros(3, dtype=np.float32)
    elif not np.all(np.isfinite(bodyrate)):
      bodyrate = np.zeros(3, dtype=np.float32)

    if ROS2_AVAILABLE and VehicleAccRatesSetpoint is not None:
      msg = VehicleAccRatesSetpoint()
      msg.timestamp = timestamp
      msg.thrust_axis_acc_sp = float(acc_p_z)
      msg.rates_sp = [
        float(bodyrate[0]),
        float(bodyrate[1]),
        float(bodyrate[2]),
      ]
      msg.sol_time = -1.0
      return msg
    else:
      # Use mock message for testing
      return NeuralControlMessage(timestamp=timestamp, acc_p_z=float(acc_p_z), bodyrate=bodyrate.copy())

  def publish(self, acc_p_z: float, bodyrate: np.ndarray, timestamp: int) -> bool:
    """
    Create and publish a control message.

    Args:
        acc_p_z: Z-axis acceleration in m/s²
        bodyrate: 3D angular velocity [wx, wy, wz] in rad/s
        timestamp: Message timestamp in microseconds

    Returns:
        True if message was published, False otherwise
    """
    # Create message
    msg = self.create_control_message(acc_p_z, bodyrate, timestamp)

    # Publish if publisher is available
    if self._publisher is not None and self._is_initialized:
      try:
        self._publisher.publish(msg)
        self._publish_count += 1
        return True
      except Exception:
        return False

    # No-op if publisher not available (doesn't crash)
    return False

  def is_initialized(self) -> bool:
    """
    Check if the publisher is initialized.

    Returns:
        True if publisher is initialized, False otherwise
    """
    return self._is_initialized

  def get_publish_count(self) -> int:
    """
    Get the number of messages published.

    Returns:
        Number of published messages
    """
    return self._publish_count

  def reset(self):
    """Reset publisher state."""
    self._publish_count = 0
