"""
ROS2 PX4 Odometry Communicator.

This module provides a communicator for receiving VehicleOdometry messages
from PX4 via ROS2.
"""

from typing import Any, Callable, Optional

from communicators.communicator_registry import (
    SensorCommunicator,
    register_communicator,
)

# Try to import ROS2 and px4_msgs - handle gracefully if not available
ROS2_AVAILABLE = False
VehicleOdometry = None

try:
    from px4_msgs.msg import VehicleOdometry

    ROS2_AVAILABLE = True
except ImportError:
    # px4_msgs not available - will use mock or skip tests
    pass


@register_communicator("ros2_px4_odometry")
class ROS2PX4OdometryCommunicator(SensorCommunicator):
    """
    ROS2 PX4 Odometry communicator for receiving VehicleOdometry messages.

    This communicator subscribes to PX4's VehicleOdometry topic and provides
    access to the latest odometry data.

    Attributes:
        _node: The ROS2 node used for creating subscriptions.
        _topic: The topic to subscribe to.
        _subscription: The ROS2 subscription object.
        _latest_message: The latest received VehicleOdometry message.
        _callback: Optional callback function for new messages.
    """

    def __init__(self, node: Any, topic: str = "/fmu/out/vehicle_odometry"):
        """
        Initialize the ROS2 PX4 Odometry communicator.

        Args:
            node: The ROS2 node to use for creating subscriptions.
            topic: The topic to subscribe to for VehicleOdometry messages.
                   Defaults to "/fmu/out/vehicle_odometry".
        """
        self._node = node
        self._topic = topic
        self._subscription: Optional[Any] = None
        self._latest_message: Optional[Any] = None
        self._callback: Optional[Callable[[Any], None]] = None

    def start(self) -> None:
        """
        Start the sensor communication.

        Creates a ROS2 subscription to the VehicleOdometry topic.
        """
        if self._subscription is not None:
            # Already started
            return

        self._subscription = self._node.create_subscription(
            VehicleOdometry if ROS2_AVAILABLE else object,
            self._topic,
            self._message_callback,
            10,  # QoS profile depth
        )

    def stop(self) -> None:
        """
        Stop the sensor communication.

        Destroys the ROS2 subscription and clears the latest message.
        """
        if self._subscription is not None:
            self._node.destroy_subscription(self._subscription)
            self._subscription = None
        self._latest_message = None

    def get_latest(self) -> Optional[Any]:
        """
        Get the latest data from the sensor.

        Returns:
            The latest VehicleOdometry message, or None if no data is available.
        """
        return self._latest_message

    def set_callback(self, callback: Callable[[Any], None]) -> None:
        """
        Set a callback function to be called when new data is received.

        Args:
            callback: A function that takes the VehicleOdometry message as its argument.
        """
        self._callback = callback

    def _message_callback(self, msg: Any) -> None:
        """
        Internal callback for handling incoming messages.

        Stores the latest message and calls the user callback if set.

        Args:
            msg: The incoming VehicleOdometry message.
        """
        self._latest_message = msg
        if self._callback is not None:
            self._callback(msg)

    @property
    def topic(self) -> str:
        """Get the subscribed topic."""
        return self._topic

    @property
    def is_started(self) -> bool:
        """Check if the communicator is started."""
        return self._subscription is not None
