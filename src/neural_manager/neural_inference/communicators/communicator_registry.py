"""
Sensor Communicator Registry Module.

This module provides the base SensorCommunicator ABC and a registry system
for managing different sensor communicator implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type


class SensorCommunicator(ABC):
    """
    Abstract base class for sensor communicators.

    Sensor communicators handle the communication with different sensor types,
    providing a unified interface for starting, stopping, and retrieving data.
    """

    @abstractmethod
    def start(self) -> None:
        """
        Start the sensor communication.

        Should initialize any required resources and begin receiving data.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        Stop the sensor communication.

        Should clean up resources and stop receiving data.
        """
        pass

    @abstractmethod
    def get_latest(self) -> Optional[Any]:
        """
        Get the latest data from the sensor.

        Returns:
            The latest sensor data, or None if no data is available.
        """
        pass

    @abstractmethod
    def set_callback(self, callback: Callable[[Any], None]) -> None:
        """
        Set a callback function to be called when new data is received.

        Args:
            callback: A function that takes the sensor data as its argument.
        """
        pass


# Global registry for sensor communicators
_COMMUNICATOR_REGISTRY: Dict[str, Type[SensorCommunicator]] = {}


def register_communicator(
    name: str,
) -> Callable[[Type[SensorCommunicator]], Type[SensorCommunicator]]:
    """
    Decorator to register a sensor communicator class.

    Args:
        name: The name to register the communicator under.

    Returns:
        A decorator function that registers the class and returns it unchanged.

    Example:
        @register_communicator("imu")
        class IMUCommunicator(SensorCommunicator):
            ...
    """

    def decorator(cls: Type[SensorCommunicator]) -> Type[SensorCommunicator]:
        if not issubclass(cls, SensorCommunicator):
            raise TypeError(f"{cls.__name__} must be a subclass of SensorCommunicator")
        _COMMUNICATOR_REGISTRY[name] = cls
        return cls

    return decorator


def get_communicator(name: str) -> Type[SensorCommunicator]:
    """
    Get a registered communicator class by name.

    Args:
        name: The name of the communicator to retrieve.

    Returns:
        The registered communicator class.

    Raises:
        KeyError: If no communicator is registered under the given name.
    """
    if name not in _COMMUNICATOR_REGISTRY:
        raise KeyError(f"No communicator registered with name '{name}'")
    return _COMMUNICATOR_REGISTRY[name]


def has_communicator(name: str) -> bool:
    """
    Check if a communicator is registered under the given name.

    Args:
        name: The name to check.

    Returns:
        True if a communicator is registered, False otherwise.
    """
    return name in _COMMUNICATOR_REGISTRY


def list_communicators() -> List[str]:
    """
    List all registered communicator names.

    Returns:
        A list of all registered communicator names.
    """
    return list(_COMMUNICATOR_REGISTRY.keys())
