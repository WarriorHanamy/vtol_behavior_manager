"""
Control layer components for neural inference module.

This module provides control output functionality including:
- Action post-processor for converting neural network output to PX4 commands
- Control publisher for publishing control messages
"""

from .control_publisher import ControlPublisher, NeuralControlMessage, ROS2_AVAILABLE

try:
    from .action_post_processor import ActionPostProcessor
except ImportError:
    ActionPostProcessor = None

__all__ = [
    "ActionPostProcessor",
    "ControlPublisher",
    "NeuralControlMessage",
    "ROS2_AVAILABLE",
]
