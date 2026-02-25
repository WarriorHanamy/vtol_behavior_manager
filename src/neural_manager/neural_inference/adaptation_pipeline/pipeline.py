"""Adaptation Pipeline for transforming sensor data into model observations.

This module provides the AdaptationPipeline class which orchestrates the
transformation of raw sensor data into observation vectors suitable for
neural network inference.
"""

from typing import Any, Dict, Optional

import numpy as np

from adaptors.adaptation_config import AdaptationConfig
from adaptors.adaptor_registry import get_adaptor
from schemas.model_schema import ModelSchema
from transforms.transform_registry import apply_transform_chain


class AdaptationPipeline:
    """Pipeline for adapting sensor data to model observation vectors.

    This class orchestrates the process of:
    1. Extracting sensor data via registered adaptors
    2. Applying transform chains to the extracted data
    3. Assembling the final observation vector

    Attributes:
        schema: The ModelSchema defining the expected observation structure.
        config: The AdaptationConfig defining field mappings.
    """

    def __init__(self, schema: ModelSchema, config: AdaptationConfig):
        """Initialize the adaptation pipeline.

        Args:
            schema: The ModelSchema defining the expected observation structure.
            config: The AdaptationConfig defining field mappings for each feature.
        """
        self.schema = schema
        self.config = config

    def adapt(
        self,
        sensor_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Adapt sensor data into a model observation vector.

        For each feature defined in the schema (in order):
        1. Look up the FieldMapping from config
        2. Get the adaptor for the sensor_type
        3. Extract the sensor_field via adaptor.get_field()
        4. Apply the transform chain via apply_transform_chain()
        5. Fill the observation at the correct offset

        Args:
            sensor_data: Dictionary mapping sensor types to raw sensor data.
            context: Optional dictionary of context values (e.g., quaternion,
                timestamp) passed to transforms.

        Returns:
            np.ndarray: Observation vector with shape (schema.total_obs_dim,).

        Raises:
            KeyError: If a required mapping, adaptor, or sensor data is missing.
            ValueError: If extracted data has wrong dimension.
        """
        if context is None:
            context = {}

        # Initialize observation vector with zeros
        observation = np.zeros(self.schema.total_obs_dim, dtype=np.float32)

        # Get feature offsets for placing data in the observation vector
        feature_offsets = self.schema.get_feature_offsets()

        # Process each feature in schema order
        for feature in self.schema.features:
            # Get the field mapping for this feature
            mapping = self.config.get_mapping(feature.name)

            # Get the adaptor class and instantiate it
            adaptor_cls = get_adaptor(mapping.sensor_type)

            # Get the raw sensor data for this sensor type
            if mapping.sensor_type not in sensor_data:
                raise KeyError(
                    f"Sensor data not found for sensor_type '{mapping.sensor_type}' "
                    f"required by feature '{feature.name}'"
                )
            raw_data = sensor_data[mapping.sensor_type]

            # Create adaptor instance and extract the field
            # Note: Adaptors are typically instantiated per-call to allow stateless classes
            adaptor = adaptor_cls()
            field_value = adaptor.get_field(mapping.sensor_field, raw_data)

            # Ensure field_value is a numpy array
            if not isinstance(field_value, np.ndarray):
                field_value = np.array(field_value, dtype=np.float32)

            # Apply the transform chain if transforms are defined
            if mapping.transforms:
                field_value = apply_transform_chain(
                    list(mapping.transforms),
                    field_value,
                    **context,
                )

            # Ensure the result has the expected dimension
            if field_value.shape != (feature.dim,):
                raise ValueError(
                    f"Feature '{feature.name}' expected dimension {feature.dim}, "
                    f"but got {field_value.shape} after processing"
                )

            # Fill observation at correct offset
            start_idx, end_idx = feature_offsets[feature.name]
            observation[start_idx:end_idx] = field_value

        return observation

    def get_context_value(
        self, key: str, context: Dict[str, Any], default: Any = None
    ) -> Any:
        """Get a value from the context dictionary with a default fallback.

        Args:
            key: The key to look up in the context.
            context: The context dictionary.
            default: Default value to return if key is not found.

        Returns:
            The value from context if key exists, otherwise the default.
        """
        return context.get(key, default)
