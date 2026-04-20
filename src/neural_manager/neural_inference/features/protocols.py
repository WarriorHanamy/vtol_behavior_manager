"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Protocols for Neural Inference Components

This module defines protocols for component interfaces.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from rclpy.qos import QoSProfile


class InferenceNodeProtocol(Protocol):
  """Protocol for neural inference node that VtolFeatureProvider interacts with.

  Defines the contract between feature provider and inference node,
  enabling loose coupling through structural subtyping.
  """

  def create_subscription(
    self,
    msg_type: Any,
    topic: str,
    callback: Callable[[Any], None],
    qos_profile: int | QoSProfile,
  ) -> Any:
    """Create a ROS2 subscription."""
    ...

  def run_inference(self) -> None:
    """Run neural inference and publish control command.

    Called by feature provider when sensor data is updated.
    Implementation should:
    1. Get features from feature provider
    2. Run policy inference
    3. Process and publish control command
    """
    ...
