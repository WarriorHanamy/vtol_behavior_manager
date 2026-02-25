"""Adaptation configuration for mapping model features to sensor data."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

from schemas.model_schema import ModelSchema


@dataclass(frozen=True)
class FieldMapping:
    """Mapping configuration for a single feature field.

    Defines how a model feature is sourced from sensor data.

    Attributes:
        feature_name: Name of the feature in the ModelSchema.
        sensor_type: Identifier for the sensor adaptor to use.
        sensor_field: Name of the field to extract from the sensor data.
        transforms: Ordered list of transform names to apply.
        scale: Optional scale factor to apply after transforms.
        description: Optional human-readable description.
    """

    feature_name: str
    sensor_type: str
    sensor_field: str
    transforms: Tuple[str, ...] = field(default_factory=tuple)
    scale: Optional[float] = None
    description: str = ""


@dataclass
class AdaptationConfig:
    """Configuration for adapting sensor data to model inputs.

    Holds the mapping between model schema features and sensor data sources.

    Attributes:
        schema: Reference to the ModelSchema being adapted.
        field_mappings: Dictionary mapping feature names to their FieldMapping.
    """

    schema: ModelSchema
    field_mappings: Dict[str, FieldMapping] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, schema: ModelSchema, path: str) -> "AdaptationConfig":
        """Load an AdaptationConfig from a YAML file.

        Args:
            schema: The ModelSchema to create adaptation for.
            path: Path to the YAML configuration file.

        Returns:
            AdaptationConfig instance loaded from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file is not valid YAML.
            KeyError: If required fields are missing.
        """
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        field_mappings: Dict[str, FieldMapping] = {}

        mappings_data = data.get("field_mappings", {})
        for feature_name, mapping_data in mappings_data.items():
            transforms = tuple(mapping_data.get("transforms", []))
            field_mappings[feature_name] = FieldMapping(
                feature_name=feature_name,
                sensor_type=mapping_data["sensor_type"],
                sensor_field=mapping_data["sensor_field"],
                transforms=transforms,
                scale=mapping_data.get("scale"),
                description=mapping_data.get("description", ""),
            )

        return cls(schema=schema, field_mappings=field_mappings)

    def validate(self, adaptor_registry) -> Tuple[bool, List[str]]:
        """Validate all field mappings against available adaptors.

        Args:
            adaptor_registry: Module or object with has_adaptor(name) function.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: List[str] = []

        # Check that all features in schema have mappings
        schema_feature_names = {f.name for f in self.schema.features}
        mapped_feature_names = set(self.field_mappings.keys())

        missing_mappings = schema_feature_names - mapped_feature_names
        for feature_name in missing_mappings:
            errors.append(f"Missing mapping for schema feature: '{feature_name}'")

        # Check for extra mappings not in schema
        extra_mappings = mapped_feature_names - schema_feature_names
        for feature_name in extra_mappings:
            errors.append(f"Mapping defined for unknown feature: '{feature_name}'")

        # Validate each mapping
        for feature_name, mapping in self.field_mappings.items():
            # Check sensor_type is registered
            if not adaptor_registry.has_adaptor(mapping.sensor_type):
                errors.append(
                    f"Feature '{feature_name}': "
                    f"sensor_type '{mapping.sensor_type}' not registered"
                )

            # Validate scale if provided
            if mapping.scale is not None and mapping.scale == 0:
                errors.append(f"Feature '{feature_name}': scale cannot be zero")

        return len(errors) == 0, errors

    def get_mapping(self, feature_name: str) -> FieldMapping:
        """Get the field mapping for a specific feature.

        Args:
            feature_name: Name of the feature to get mapping for.

        Returns:
            FieldMapping for the requested feature.

        Raises:
            KeyError: If no mapping exists for the feature name.
        """
        if feature_name not in self.field_mappings:
            raise KeyError(f"No mapping found for feature: '{feature_name}'")
        return self.field_mappings[feature_name]
