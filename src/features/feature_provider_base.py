"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Feature Provider Base Module

This module provides a base class for feature providers with auto-validation
and convention-based feature discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import yaml


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FeatureSpec:
    """
    Specification for a single feature.

    Attributes:
        name: Feature name
        dim: Feature dimension
        dtype: Data type (e.g., "float32", "float64")
        description: Human-readable description (optional)
    """

    name: str
    dim: int
    dtype: str
    description: Optional[str] = None


@dataclass
class FeatureValidationResult:
    """
    Result of validating a feature implementation.

    Attributes:
        feature_name: Name of the feature being validated
        passed: Whether validation passed
        error_message: Error message if validation failed
        expected_dim: Expected dimension from metadata
        actual_dim: Actual dimension from implementation
    """

    feature_name: str
    passed: bool
    error_message: Optional[str]
    expected_dim: int
    actual_dim: Optional[int]


# =============================================================================
# Main Class
# =============================================================================


class FeatureProviderBase:
    """
    Base class for feature providers with auto-validation and convention-based discovery.

    This class provides:
    1. Automatic validation of feature implementations against metadata
    2. Convention-based discovery using get_{feature_name} methods
    3. Clear validation reporting at initialization
    4. Methods to retrieve single or all features
    """

    def __init__(self, metadata_path: Path | str):
        """
        Initialize the feature provider.

        Args:
            metadata_path: Path to observation_metadata.yaml file
        """
        self._metadata_path = Path(metadata_path)
        self._metadata: List[FeatureSpec] = []
        self._validation_results: List[FeatureValidationResult] = []

        # Load metadata
        self._metadata = self._load_metadata()

        # Validate implementations
        self._validation_results = self._validate_implementations()

        # Print validation report
        self._print_validation_report(self._validation_results)

    def _load_metadata(self) -> List[FeatureSpec]:
        """
        Parse observation_metadata.yaml and return list of FeatureSpec.

        Returns:
            List of FeatureSpec objects parsed from metadata file
        """
        with open(self._metadata_path, "r") as f:
            data = yaml.safe_load(f)

        features = []
        for feature_data in data.get("features", []):
            spec = FeatureSpec(
                name=feature_data["name"],
                dim=feature_data["dim"],
                dtype=feature_data["dtype"],
                description=feature_data.get("description"),
            )
            features.append(spec)

        return features

    def _validate_implementations(self) -> List[FeatureValidationResult]:
        """
        Validate feature implementations using convention-based discovery.

        Discovers feature methods using get_{feature_name} convention and
        validates that implementation output dimension matches metadata.

        Returns:
            List of FeatureValidationResult objects for all features
        """
        results = []

        for spec in self._metadata:
            method_name = f"get_{spec.name}"

            # Check if method exists
            if not hasattr(self, method_name):
                results.append(
                    FeatureValidationResult(
                        feature_name=spec.name,
                        passed=False,
                        error_message=f"Method '{method_name}' not found",
                        expected_dim=spec.dim,
                        actual_dim=None,
                    )
                )
                continue

            # Get the method
            method = getattr(self, method_name)

            # Try to call the method and check output dimension
            try:
                output = method()
                actual_dim = len(output) if hasattr(output, "__len__") else 1

                if actual_dim == spec.dim:
                    results.append(
                        FeatureValidationResult(
                            feature_name=spec.name,
                            passed=True,
                            error_message=None,
                            expected_dim=spec.dim,
                            actual_dim=actual_dim,
                        )
                    )
                else:
                    results.append(
                        FeatureValidationResult(
                            feature_name=spec.name,
                            passed=False,
                            error_message=(
                                f"Dimension mismatch: expected {spec.dim}, "
                                f"got {actual_dim}"
                            ),
                            expected_dim=spec.dim,
                            actual_dim=actual_dim,
                        )
                    )
            except Exception as e:
                results.append(
                    FeatureValidationResult(
                        feature_name=spec.name,
                        passed=False,
                        error_message=f"Error calling method: {str(e)}",
                        expected_dim=spec.dim,
                        actual_dim=None,
                    )
                )

        return results

    def _print_validation_report(self, results: List[FeatureValidationResult]) -> None:
        """
        Print clear pass/fail indicators for each feature.

        Args:
            results: List of FeatureValidationResult objects
        """
        print("\n" + "=" * 60)
        print("Feature Validation Report")
        print("=" * 60)

        for result in results:
            status = "PASS" if result.passed else "FAIL"
            print(f"\n{status}: {result.feature_name}")

            if not result.passed:
                print(f"  Error: {result.error_message}")
                print(f"  Expected dimension: {result.expected_dim}")
                if result.actual_dim is not None:
                    print(f"  Actual dimension: {result.actual_dim}")

        # Summary
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        print("\n" + "-" * 60)
        print(f"Summary: {passed}/{total} features passed validation")
        print("=" * 60 + "\n")

    def get_all_features(self) -> np.ndarray:
        """
        Concatenate all features in metadata order.

        Returns:
            Numpy array with all features concatenated
        """
        features_list = [getattr(self, f"get_{spec.name}")() for spec in self._metadata]

        return np.concatenate(features_list)

    def get_feature(self, name: str) -> np.ndarray:
        """
        Retrieve a single feature by name with error checking.

        Args:
            name: Name of the feature to retrieve

        Returns:
            Numpy array with the feature vector

        Raises:
            ValueError: If feature name is not found in metadata
        """
        # Check if feature exists in metadata
        spec = next((s for s in self._metadata if s.name == name), None)

        if spec is None:
            raise ValueError(
                f"Feature '{name}' not found in metadata. "
                f"Available features: {[s.name for s in self._metadata]}"
            )

        # Get the feature
        method_name = f"get_{name}"
        method = getattr(self, method_name)
        feature = method()

        # Validate dimension
        actual_dim = len(feature) if hasattr(feature, "__len__") else 1
        if actual_dim != spec.dim:
            raise ValueError(
                f"Feature '{name}' dimension mismatch: "
                f"expected {spec.dim}, got {actual_dim}"
            )

        return feature

    def get_validation_report(self) -> List[FeatureValidationResult]:
        """
        Get validation results for programmatic access.

        Returns:
            List of FeatureValidationResult objects
        """
        return self._validation_results
