"""Adaptor Registry for sensor adapters."""

from typing import Callable, Dict, List, Type

from adaptors.sensor_adapter import SensorAdapter


# Global registry for sensor adapters
_ADAPTOR_REGISTRY: Dict[str, Type[SensorAdapter]] = {}


def register_adaptor(name: str) -> Callable[[Type[SensorAdapter]], Type[SensorAdapter]]:
    """Decorator to register a sensor adapter class.

    Args:
        name: Unique identifier for the adapter.

    Returns:
        Decorator function that registers the adapter class.

    Example:
        @register_adaptor("imu")
        class ImuAdapter(SensorAdapter):
            ...
    """

    def decorator(cls: Type[SensorAdapter]) -> Type[SensorAdapter]:
        _ADAPTOR_REGISTRY[name] = cls
        return cls

    return decorator


def get_adaptor(name: str) -> Type[SensorAdapter]:
    """Get a registered adapter class by name.

    Args:
        name: Unique identifier for the adapter.

    Returns:
        Type[SensorAdapter]: The registered adapter class.

    Raises:
        KeyError: If no adapter is registered with the given name.
    """
    if name not in _ADAPTOR_REGISTRY:
        raise KeyError(
            f"No adapter registered with name '{name}'. "
            f"Available adapters: {list(_ADAPTOR_REGISTRY.keys())}"
        )
    return _ADAPTOR_REGISTRY[name]


def has_adaptor(name: str) -> bool:
    """Check if an adapter is registered with the given name.

    Args:
        name: Unique identifier for the adapter.

    Returns:
        bool: True if adapter is registered, False otherwise.
    """
    return name in _ADAPTOR_REGISTRY


def list_adaptors() -> List[str]:
    """List all registered adapter names.

    Returns:
        List[str]: List of registered adapter identifiers.
    """
    return list(_ADAPTOR_REGISTRY.keys())


def clear_registry() -> None:
    """Clear all registered adapters.

    This is primarily useful for testing.
    """
    _ADAPTOR_REGISTRY.clear()
