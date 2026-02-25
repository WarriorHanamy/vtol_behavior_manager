"""
Sensor Communicators Module.

This module provides sensor communicator interfaces and a registry system
for managing different sensor communicator implementations.
"""

from communicators.communicator_registry import (
    SensorCommunicator,
    _COMMUNICATOR_REGISTRY,
    register_communicator,
    get_communicator,
    has_communicator,
    list_communicators,
)
from communicators.ros2_px4_odometry import (
    ROS2PX4OdometryCommunicator,
    ROS2_AVAILABLE,
)

__all__ = [
    "SensorCommunicator",
    "_COMMUNICATOR_REGISTRY",
    "register_communicator",
    "get_communicator",
    "has_communicator",
    "list_communicators",
    "ROS2PX4OdometryCommunicator",
    "ROS2_AVAILABLE",
]
