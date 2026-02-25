"""
PX4 Vehicle Odometry Adapter for neural inference module.

Provides data extraction from PX4 VehicleOdometry messages.
"""

from typing import Any, List

import numpy as np

from .sensor_adapter import SensorAdapter
from .adaptor_registry import register_adaptor


@register_adaptor("px4_vehicle_odometry")
class PX4VehicleOdometryAdapter(SensorAdapter):
    """Adapter for PX4 VehicleOdometry messages.

    Extracts fields from PX4's VehicleOdometry message format:
    - position_ned: [N, E, D] position in NED frame (meters)
    - velocity_ned: [N, E, D] velocity in NED frame (m/s)
    - orientation_quat: [w, x, y, z] quaternion (Hamilton convention)
    - angular_velocity_frd: [roll, pitch, yaw] rates in FRD frame (rad/s)
    - timestamp_us: timestamp in microseconds
    """

    @property
    def sensor_type(self) -> str:
        """Return the sensor type identifier."""
        return "px4_vehicle_odometry"

    def get_available_fields(self) -> List[str]:
        """Return list of available field names."""
        return [
            "position_ned",
            "velocity_ned",
            "orientation_quat",
            "angular_velocity_frd",
            "timestamp_us",
        ]

    def get_field(self, field_name: str, raw_data: Any) -> np.ndarray:
        """Extract a specific field from VehicleOdometry data.

        Args:
            field_name: Name of the field to extract.
            raw_data: Object with VehicleOdometry-like attributes.

        Returns:
            np.ndarray: Extracted field data.

        Raises:
            KeyError: If field_name is not available.
        """
        if field_name == "position_ned":
            return np.array(raw_data.position, dtype=np.float32)
        elif field_name == "velocity_ned":
            return np.array(raw_data.velocity, dtype=np.float32)
        elif field_name == "orientation_quat":
            # PX4 uses [w, x, y, z] Hamilton convention
            return np.array(raw_data.q, dtype=np.float32)
        elif field_name == "angular_velocity_frd":
            return np.array(raw_data.angular_velocity, dtype=np.float32)
        elif field_name == "timestamp_us":
            return np.array([raw_data.timestamp], dtype=np.int64)
        else:
            raise KeyError(
                f"Unknown field '{field_name}'. Available fields: {self.get_available_fields()}"
            )

    def get_timestamp(self, raw_data: Any) -> int:
        """Extract timestamp from raw data.

        Args:
            raw_data: Object with timestamp attribute.

        Returns:
            int: Timestamp in microseconds.
        """
        return raw_data.timestamp
