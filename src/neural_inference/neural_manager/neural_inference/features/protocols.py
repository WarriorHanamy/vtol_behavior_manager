"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Protocols for Neural Inference Components

This module defines protocols for component interfaces.
Note: ROS subscriptions are managed by NeuralControlNode, not by feature providers.
Feature providers no longer hold references to the ROS node.
"""

from __future__ import annotations
