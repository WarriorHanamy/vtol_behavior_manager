"""Sensor Adaptors module for neural inference."""

from adaptors.sensor_adapter import SensorAdapter
from adaptors.adaptor_registry import (
    register_adaptor,
    get_adaptor,
    has_adaptor,
    list_adaptors,
    clear_registry,
)
from adaptors.px4_vehicle_odometry import PX4VehicleOdometryAdapter
from adaptors.adaptation_config import FieldMapping, AdaptationConfig

__all__ = [
    "SensorAdapter",
    "register_adaptor",
    "get_adaptor",
    "has_adaptor",
    "list_adaptors",
    "clear_registry",
    "PX4VehicleOdometryAdapter",
    "FieldMapping",
    "AdaptationConfig",
]
