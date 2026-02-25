"""Sensor Adapter Abstract Base Class for neural inference module."""

from abc import ABC, abstractmethod
from typing import Any, List

import numpy as np


class SensorAdapter(ABC):
    """Abstract base class for sensor data adapters.

    Adapters convert raw sensor data into a standardized format
    for neural network inference.
    """

    @property
    @abstractmethod
    def sensor_type(self) -> str:
        """Return the sensor type identifier.

        Returns:
            str: Unique identifier for this sensor type.
        """
        pass

    @abstractmethod
    def get_available_fields(self) -> List[str]:
        """Return list of available field names.

        Returns:
            List[str]: List of field names that can be extracted from raw data.
        """
        pass

    @abstractmethod
    def get_field(self, field_name: str, raw_data: Any) -> np.ndarray:
        """Extract a specific field from raw data.

        Args:
            field_name: Name of the field to extract.
            raw_data: Raw sensor data.

        Returns:
            np.ndarray: Extracted field data as numpy array.

        Raises:
            KeyError: If field_name is not available.
        """
        pass

    @abstractmethod
    def get_timestamp(self, raw_data: Any) -> int:
        """Extract timestamp from raw data.

        Args:
            raw_data: Raw sensor data.

        Returns:
            int: Timestamp in nanoseconds.
        """
        pass
