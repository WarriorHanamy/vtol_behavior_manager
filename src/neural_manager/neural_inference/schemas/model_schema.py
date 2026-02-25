"""Model schema definitions for neural inference module."""

from dataclasses import dataclass
from typing import Dict, Tuple

import yaml


@dataclass(frozen=True)
class FeatureSpec:
    """Specification for a single feature in the model schema.

    Attributes:
        name: Unique identifier for the feature.
        dim: Dimensionality of the feature vector.
        description: Optional human-readable description.
    """

    name: str
    dim: int
    description: str = ""


@dataclass(frozen=True)
class ModelSchema:
    """Schema definition for a neural model.

    Defines the structure of input features and their dimensions.

    Attributes:
        schema_version: Version string for the schema format.
        model_name: Name identifier for the model.
        features: Tuple of feature specifications.
    """

    schema_version: str
    model_name: str
    features: Tuple[FeatureSpec, ...]

    @property
    def total_obs_dim(self) -> int:
        """Calculate total observation dimension across all features.

        Returns:
            Sum of all feature dimensions.
        """
        return sum(f.dim for f in self.features)

    def get_feature_offsets(self) -> Dict[str, Tuple[int, int]]:
        """Calculate start and end indices for each feature in the observation vector.

        Returns:
            Dictionary mapping feature names to (start_index, end_index) tuples.
            The end_index is exclusive (can be used for slicing).
        """
        offsets: Dict[str, Tuple[int, int]] = {}
        current_offset = 0

        for feature in self.features:
            offsets[feature.name] = (current_offset, current_offset + feature.dim)
            current_offset += feature.dim

        return offsets

    @classmethod
    def from_yaml(cls, path: str) -> "ModelSchema":
        """Load a ModelSchema from a YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            ModelSchema instance loaded from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file is not valid YAML.
            KeyError: If required fields are missing.
        """
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        schema_version = data["schema_version"]
        model_name = data["model_name"]

        features_list = data.get("features", [])
        features = tuple(
            FeatureSpec(
                name=feat["name"],
                dim=feat["dim"],
                description=feat.get("description", ""),
            )
            for feat in features_list
        )

        return cls(
            schema_version=schema_version,
            model_name=model_name,
            features=features,
        )

    def get_feature_by_name(self, name: str) -> FeatureSpec:
        """Retrieve a feature specification by name.

        Args:
            name: The name of the feature to retrieve.

        Returns:
            The FeatureSpec with the given name.

        Raises:
            KeyError: If no feature with the given name exists.
        """
        for feature in self.features:
            if feature.name == name:
                return feature
        raise KeyError(f"Feature '{name}' not found in schema")
