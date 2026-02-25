"""
Mock implementations for ROS2 components.

This module provides mock classes that simulate ROS2 behavior
for isolated unit testing without requiring a running ROS2 system.
"""

import time
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import Mock
from collections import deque
import numpy as np


class MockLogger:
    """
    Mock ROS2 logger with call tracking.

    Tracks all log calls for verification in tests.
    """

    def __init__(self):
        self.info_calls: List[str] = []
        self.warning_calls: List[str] = []
        self.error_calls: List[str] = []
        self.debug_calls: List[str] = []
        self.fatal_calls: List[str] = []

    def info(self, msg: str, *args, **kwargs):
        """Log info message."""
        self.info_calls.append(msg)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message."""
        self.warning_calls.append(msg)

    def error(self, msg: str, *args, **kwargs):
        """Log error message."""
        self.error_calls.append(msg)

    def debug(self, msg: str, *args, **kwargs):
        """Log debug message."""
        self.debug_calls.append(msg)

    def fatal(self, msg: str, *args, **kwargs):
        """Log fatal message."""
        self.fatal_calls.append(msg)

    def set_level(self, level):
        """Set log level (no-op for mock)."""
        pass

    def get_effective_level(self):
        """Get effective log level."""
        return 0

    def reset(self):
        """Clear all logged calls."""
        self.info_calls.clear()
        self.warning_calls.clear()
        self.error_calls.clear()
        self.debug_calls.clear()
        self.fatal_calls.clear()


class MockPublisher:
    """
    Mock ROS2 publisher.

    Tracks published messages for verification in tests.
    """

    def __init__(self, msg_type: Any, topic: str, qos_profile: int = 10):
        self.msg_type = msg_type
        self.topic = topic
        self.qos_profile = qos_profile
        self.published: List[Any] = []
        self.publish_count = 0
        self._is_active = True

    def publish(self, msg: Any):
        """Publish a message (store for verification)."""
        if self._is_active:
            self.published.append(msg)
            self.publish_count += 1

    def get_last_published(self) -> Optional[Any]:
        """Get the last published message."""
        return self.published[-1] if self.published else None

    def get_published_count(self) -> int:
        """Get total number of published messages."""
        return self.publish_count

    def clear(self):
        """Clear published message history."""
        self.published.clear()
        self.publish_count = 0

    def unregister(self):
        """Unregister publisher."""
        self._is_active = False


class MockSubscription:
    """
    Mock ROS2 subscription.

    Simulates callback behavior for testing subscribers.
    """

    def __init__(self, msg_type: Any, topic: str, callback: Callable,
                 qos_profile: int = 10):
        self.msg_type = msg_type
        self.topic = topic
        self.callback = callback
        self.qos_profile = qos_profile
        self.received: List[Any] = []
        self.receive_count = 0
        self._is_active = True

    def trigger(self, msg: Any):
        """Manually trigger the subscription callback."""
        if self._is_active:
            self.received.append(msg)
            self.receive_count += 1
            self.callback(msg)

    def get_last_received(self) -> Optional[Any]:
        """Get the last received message."""
        return self.received[-1] if self.received else None

    def get_received_count(self) -> int:
        """Get total number of received messages."""
        return self.receive_count

    def clear(self):
        """Clear received message history."""
        self.received.clear()
        self.receive_count = 0

    def unregister(self):
        """Unregister subscription."""
        self._is_active = False


class MockNode:
    """
    Mock rclpy.node.Node for testing.

    Simulates ROS2 node behavior including publisher/subscriber creation,
    timer creation, and lifecycle management.
    """

    def __init__(self, node_name: str = "mock_node"):
        self._node_name = node_name
        self._logger = MockLogger()
        self._publishers: Dict[str, MockPublisher] = {}
        self._subscribers: Dict[str, MockSubscription] = {}
        self._timers: Dict[str, MockTimer] = {}
        self._parameters: Dict[str, Any] = {}
        self._is_active = False

    def get_name(self) -> str:
        """Get node name."""
        return self._node_name

    def get_logger(self) -> MockLogger:
        """Get mock logger."""
        return self._logger

    def create_publisher(self, msg_type: Any, topic: str,
                         qos_profile: int = 10) -> MockPublisher:
        """Create a mock publisher."""
        publisher = MockPublisher(msg_type, topic, qos_profile)
        self._publishers[topic] = publisher
        return publisher

    def create_subscription(self, msg_type: Any, topic: str,
                            callback: Callable, qos_profile: int = 10) -> MockSubscription:
        """Create a mock subscription."""
        subscription = MockSubscription(msg_type, topic, callback, qos_profile)
        self._subscribers[topic] = subscription
        return subscription

    def create_timer(self, period: float, callback: Callable,
                     clock=None) -> 'MockTimer':
        """Create a mock timer."""
        timer = MockTimer(period, callback, self)
        timer_id = f"timer_{len(self._timers)}"
        self._timers[timer_id] = timer
        return timer

    def get_publisher(self, topic: str) -> Optional[MockPublisher]:
        """Get publisher by topic."""
        return self._publishers.get(topic)

    def get_subscription(self, topic: str) -> Optional[MockSubscription]:
        """Get subscription by topic."""
        return self._subscribers.get(topic)

    def declare_parameter(self, name: str, value: Any) -> None:
        """Declare a parameter."""
        self._parameters[name] = value

    def get_parameter(self, name: str) -> Optional[Any]:
        """Get a parameter value."""
        return self._parameters.get(name)

    def set_parameter(self, name: str, value: Any) -> bool:
        """Set a parameter value."""
        self._parameters[name] = value
        return True

    def destroy_publisher(self, publisher: MockPublisher) -> None:
        """Destroy a publisher."""
        publisher.unregister()
        if publisher.topic in self._publishers:
            del self._publishers[publisher.topic]

    def destroy_subscription(self, subscription: MockSubscription) -> None:
        """Destroy a subscription."""
        subscription.unregister()
        if subscription.topic in self._subscribers:
            del self._subscribers[subscription.topic]

    def destroy_timer(self, timer: 'MockTimer') -> None:
        """Destroy a timer."""
        timer.cancel()
        for timer_id, t in list(self._timers.items()):
            if t is timer:
                del self._timers[timer_id]

    def reset(self):
        """Reset node state."""
        self._logger.reset()
        for publisher in self._publishers.values():
            publisher.clear()
        for subscription in self._subscribers.values():
            subscription.clear()
        for timer in self._timers.values():
            timer.reset()


class MockTimer:
    """
    Mock ROS2 timer.

    Simulates timer behavior for testing periodic callbacks.
    """

    def __init__(self, period: float, callback: Callable, node: MockNode):
        self.period = period
        self.callback = callback
        self._node = node
        self._is_running = False
        self._call_count = 0
        self._last_call_time: Optional[float] = None

    def start(self):
        """Start the timer."""
        self._is_running = True

    def stop(self):
        """Stop the timer."""
        self._is_running = False

    def cancel(self):
        """Cancel the timer."""
        self._is_running = False

    def is_running(self) -> bool:
        """Check if timer is running."""
        return self._is_running

    def trigger(self):
        """Manually trigger timer callback."""
        if self._is_running:
            self._call_count += 1
            self._last_call_time = time.time()
            self.callback()

    def get_call_count(self) -> int:
        """Get number of times callback was triggered."""
        return self._call_count

    def reset(self):
        """Reset timer state."""
        self._call_count = 0
        self._last_call_time = None
        self._is_running = False


class MockClock:
    """
    Mock ROS2 clock for time-based operations.
    """

    def __init__(self):
        self._current_time = 0.0

    def now(self) -> 'MockTime':
        """Get current time."""
        return MockTime(self._current_time)

    def advance(self, seconds: float):
        """Advance clock by specified seconds."""
        self._current_time += seconds

    def set_time(self, seconds: float):
        """Set clock to specific time."""
        self._current_time = seconds


class MockTime:
    """Mock ROS2 Time object."""

    def __init__(self, nanoseconds: float):
        self._nanoseconds = nanoseconds

    def to_sec(self) -> float:
        """Convert to seconds."""
        return self._nanoseconds

    def nanoseconds(self) -> int:
        """Get nanoseconds."""
        return int(self._nanoseconds * 1e9)


class MockQoSProfile:
    """Mock QoS profile."""

    def __init__(self, depth: int = 10):
        self.depth = depth

    @staticmethod
    def sensor_data() -> 'MockQoSProfile':
        """Get sensor data QoS profile."""
        return MockQoSProfile(depth=5)

    @staticmethod
    def parameters() -> 'MockQoSProfile':
        """Get parameters QoS profile."""
        return MockQoSProfile(depth=10)


# =============================================================================
# Utility Functions
# =============================================================================

def create_mock_vehicle_odometry(
    timestamp: int = 0,
    position: Optional[np.ndarray] = None,
    velocity: Optional[np.ndarray] = None,
    q: Optional[np.ndarray] = None,
    angular_velocity: Optional[np.ndarray] = None
) -> Mock:
    """
    Create a mock VehicleOdometry message.

    Args:
        timestamp: Message timestamp in microseconds
        position: NED position [North, East, Down] in meters
        velocity: NED velocity [North, East, Down] in m/s
        q: Quaternion [w, x, y, z]
        angular_velocity: Body angular velocity [roll, pitch, yaw] in rad/s

    Returns:
        Mock VehicleOdometry message
    """
    msg = Mock()
    msg.timestamp = timestamp
    msg.position = position if position is not None else np.array([0.0, 0.0, -3.0], dtype=np.float32)
    msg.q = q if q is not None else np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    msg.velocity = velocity if velocity is not None else np.array([0.0, 0.0, 0.0], dtype=np.float32)
    msg.angular_velocity = angular_velocity if angular_velocity is not None else np.array([0.0, 0.0, 0.0], dtype=np.float32)
    msg.position_variance = np.array([0.01, 0.01, 0.01], dtype=np.float32)
    msg.orientation_variance = np.array([0.001, 0.001, 0.001], dtype=np.float32)
    return msg


def create_mock_rates_setpoint(
    timestamp: int = 0,
    thrust_body: Optional[np.ndarray] = None,
    roll: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0
) -> Mock:
    """
    Create a mock VehicleRatesSetpoint message.

    Args:
        timestamp: Message timestamp in microseconds
        thrust_body: Body thrust [x, y, z] in N
        roll: Roll rate setpoint in rad/s
        pitch: Pitch rate setpoint in rad/s
        yaw: Yaw rate setpoint in rad/s

    Returns:
        Mock VehicleRatesSetpoint message
    """
    msg = Mock()
    msg.timestamp = timestamp
    msg.thrust_body = thrust_body if thrust_body is not None else np.array([0.0, 0.0, 15.0], dtype=np.float32)
    msg.roll = roll
    msg.pitch = pitch
    msg.yaw = yaw
    return msg


def create_mock_thrust_acc_setpoint(
    timestamp: int = 0,
    thrust_body: Optional[np.ndarray] = None,
    roll_rate: float = 0.0,
    pitch_rate: float = 0.0,
    yaw_rate: float = 0.0
) -> Mock:
    """
    Create a mock VehicleThrustAccSetpoint message.

    Args:
        timestamp: Message timestamp in microseconds
        thrust_body: Body thrust acceleration [x, y, z] in m/s^2
        roll_rate: Roll rate setpoint in rad/s
        pitch_rate: Pitch rate setpoint in rad/s
        yaw_rate: Yaw rate setpoint in rad/s

    Returns:
        Mock VehicleThrustAccSetpoint message
    """
    msg = Mock()
    msg.timestamp = timestamp
    msg.thrust_body = thrust_body if thrust_body is not None else np.array([0.0, 0.0, 15.0], dtype=np.float32)
    msg.roll_rate = roll_rate
    msg.pitch_rate = pitch_rate
    msg.yaw_rate = yaw_rate
    return msg
