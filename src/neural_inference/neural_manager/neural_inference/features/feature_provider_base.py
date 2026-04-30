"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Feature Provider Base Module

This module provides a base class for feature providers with auto-validation
and convention-based feature discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from .revision_discoverer import RevisionDiscoverer

# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FeatureSpec:
  """Specification for a single feature.

  Attributes:
      name: Feature name
      dim: Feature dimension

  """

  name: str
  dim: int


@dataclass
class FeatureValidationResult:
  """Result of validating a feature implementation.

  Attributes:
      feature_name: Name of the feature being validated
      passed: Whether validation passed
      error_message: Error message if validation failed
      expected_dim: Expected dimension from metadata
      actual_dim: Actual dimension from implementation

  """

  feature_name: str
  passed: bool
  error_message: str | None
  expected_dim: int
  actual_dim: int | None


# =============================================================================
# Main Class
# =============================================================================


class FeatureProviderBase:
  """Base class for feature providers with auto-validation and convention-based discovery.

  This class provides:
  1. Automatic validation of feature implementations against metadata
  2. Convention-based discovery using get_{feature_name} methods
  3. Clear validation reporting at initialization
  4. Methods to retrieve single or all features
  """

  def __init__(self, metadata_path: Path | str):
    """Initialize the feature provider.

    Args:
        metadata_path: Path to observation_metadata.yaml file

    """
    self._metadata_path = Path(metadata_path)
    self._metadata: list[FeatureSpec] = []
    self._validation_results: list[FeatureValidationResult] = []

    # Load metadata
    self._metadata = self._load_metadata()

    # Validate implementations
    self._validation_results = self._validate_implementations()

    # Print validation report
    self._print_validation_report(self._validation_results)

  @classmethod
  def from_latest_revision(cls, artifacts_root: Path | str, task: str):
    """Create a FeatureProviderBase instance by auto-discovering the latest revision.

    This method uses RevisionDiscoverer to find the latest valid revision for
    the given task, then initializes a FeatureProviderBase instance with the
    metadata from that revision.

    Args:
        artifacts_root: Base directory containing policies/ subdirectory
        task: Task name (e.g., "vtol_hover")

    Returns:
        An initialized FeatureProviderBase instance

    Raises:
        FileNotFoundError: If no valid revision is found for the given task

    Examples:
        >>> provider = FeatureProviderBase.from_latest_revision(
        ...     "/path/to/artifacts", "vtol_hover"
        ... )

    """
    # Discover the latest revision
    latest_revision = RevisionDiscoverer.discover_latest(artifacts_root, task)

    # Handle case when no valid revision found
    if latest_revision is None:
      raise FileNotFoundError(
        f"No valid revision found for task '{task}' in artifacts_root '{artifacts_root}'. "
        f"Ensure that '{Path(artifacts_root)}/policies/{task}/' exists and "
        f"contains at least one valid revision directory with both "
        f"'model.onnx' and 'observations_metadata.yaml' files."
      )

    # Construct metadata path and create instance
    metadata_path = latest_revision / "observations_metadata.yaml"

    return cls(metadata_path)

  def _load_metadata(self) -> list[FeatureSpec]:
    """Parse observation_metadata.yaml and return list of FeatureSpec.

    Expects format: {'low_dim': [{'name': '...', 'dim': N}, ...]}

    Returns:
        list of FeatureSpec objects parsed from metadata file

    """
    with open(self._metadata_path) as f:
      data = yaml.safe_load(f)

    features = []
    for feature_data in data.get("low_dim", []):
      spec = FeatureSpec(
        name=feature_data["name"],
        dim=feature_data["dim"],
      )
      features.append(spec)

    return features

  def _validate_implementations(self) -> list[FeatureValidationResult]:
    """Validate feature implementations using convention-based discovery.

    Discovers feature methods using get_{feature_name} convention and
    validates that implementation output dimension matches metadata.

    Returns:
        list of FeatureValidationResult objects for all features

    Raises:
        RuntimeError: If any feature validation fails

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
              error_message=(f"Dimension mismatch: expected {spec.dim}, got {actual_dim}"),
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

    # Raise error if any validation failed
    self._raise_on_validation_failure(results)

    return results

  @staticmethod
  def _raise_on_validation_failure(
    results: list[FeatureValidationResult],
  ) -> None:
    """Raise RuntimeError if any validation failed.

    Args:
        results: list of FeatureValidationResult objects

    Raises:
        RuntimeError: If any feature validation fails

    """
    failed_results = [r for r in results if not r.passed]
    if not failed_results:
      return

    error_lines = [f"Feature validation failed for {len(failed_results)} feature(s):"]
    for result in failed_results:
      error_lines.append(f"  - {result.feature_name}: {result.error_message}")

    raise RuntimeError("\n".join(error_lines))

  def _print_validation_report(self, results: list[FeatureValidationResult]) -> None:
    """Print clear pass/fail indicators for each feature.

    Args:
        results: list of FeatureValidationResult objects

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
    """Concatenate all features in metadata order.

    Returns:
        Numpy array with all features concatenated

    """
    features_list = [getattr(self, f"get_{spec.name}")() for spec in self._metadata]

    return np.concatenate(features_list)

  def get_feature(self, name: str) -> np.ndarray:
    """Retrieve a single feature by name with error checking.

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
      available = [s.name for s in self._metadata]
      raise ValueError(f"Feature '{name}' not found in metadata. Available features: {available}")

    # Get the feature
    method_name = f"get_{name}"
    method = getattr(self, method_name)
    feature = method()

    # Validate dimension
    actual_dim = len(feature) if hasattr(feature, "__len__") else 1
    if actual_dim != spec.dim:
      raise ValueError(
        f"Feature '{name}' dimension mismatch: expected {spec.dim}, got {actual_dim}"
      )

    return feature

  def get_goal_str(self) -> str:
    """Get human-readable goal string for logging.

    Returns:
        String representation of the current goal, or empty string if none.

    """
    return ""

  def get_feature_specs(self) -> list[FeatureSpec]:
    """Get feature specifications list.

    Returns:
        list of FeatureSpec objects

    """
    return self._metadata.copy()

  def get_validation_report(self) -> list[FeatureValidationResult]:
    """Get validation results for programmatic access.

    Returns:
        list of FeatureValidationResult objects

    """
    return self._validation_results
