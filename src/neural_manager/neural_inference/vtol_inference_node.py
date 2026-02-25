#!/usr/bin/env python3
"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

VTOL Neural Inference Node Module

This module provides a neural inference node that integrates ModelDiscoverer
and VtolFeatureProvider for automatic model discovery and feature-based inference.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import yaml

# Add src directory to path for imports
if str(Path(__file__).parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from features.vtol_feature_provider import VtolFeatureProvider
from neural_manager.model_discovery import ModelDiscoverer

# Constants
METADATA_FILENAME = "observation_metadata.yaml"


class VtolNeuralInferenceNode:
    """
    VTOL neural inference node integrating ModelDiscoverer and VtolFeatureProvider.

    This class provides:
    1. Automatic model discovery from configurable search paths
    2. Feature provider initialization with discovered model metadata
    3. Inference for single feature or all features
    4. Graceful handling of None feature returns with zero-padding
    5. List available models in search paths

    Attributes:
        _model_discoverer: ModelDiscoverer instance for model discovery
        _feature_provider: VtolFeatureProvider instance for feature computation
        _discovered_model: DiscoveredModel with metadata and session
    """

    def __init__(
        self,
        search_paths: List[Path | str] | Path | str,
        task_name: Optional[str] = None,
        skip_model_discovery: bool = False,
    ):
        """
        Initialize the VTOL neural inference node.

        Args:
            search_paths: List of directories to search for models (or single path)
            task_name: Optional task name for task-specific model discovery
            skip_model_discovery: If True, skip model discovery (for testing list_available_models)
        """
        # Normalize search_paths to always be a list
        if isinstance(search_paths, (Path, str)):
            search_paths = [search_paths]

        # Initialize ModelDiscoverer with configurable search paths
        self._model_discoverer = ModelDiscoverer(search_paths=search_paths)
        self._feature_provider: Optional[VtolFeatureProvider] = None
        self._discovered_model = None

        # Skip model discovery if requested (for testing list_available_models)
        if skip_model_discovery:
            return

        # Discover and load model
        self._discovered_model = self._model_discoverer.discover_and_load(
            model_name=task_name
        )

        # Initialize VtolFeatureProvider with metadata from discovered model
        if self._discovered_model is not None:
            # Find the observation_metadata.yaml file using the same search strategy as ModelDiscoverer
            metadata_path = self._find_metadata_path(task_name)

            if metadata_path is not None:
                self._feature_provider = VtolFeatureProvider(
                    metadata_path=metadata_path
                )

    def _find_metadata_path(self, task_name: Optional[str] = None) -> Optional[Path]:
        """
        Find observation_metadata.yaml file using ModelDiscoverer's search strategy.

        Uses the same search strategy as ModelDiscoverer._find_metadata_file():
        1. Task-specific search: Look in task_name/observation_metadata.yaml
        2. Default search: Look in search_path/observation_metadata.yaml

        Args:
            task_name: Optional task name for task-specific search

        Returns:
            Path to observation_metadata.yaml file, or None if not found
        """
        # Iterate through search paths in order
        for search_path in self._model_discoverer._search_paths:
            # Try task-specific path first
            if task_name is not None:
                task_specific_path = search_path / task_name / METADATA_FILENAME
                if task_specific_path.exists():
                    if self._is_valid_metadata_file(task_specific_path):
                        return task_specific_path

            # Try default path
            default_path = search_path / METADATA_FILENAME
            if default_path.exists():
                if self._is_valid_metadata_file(default_path):
                    return default_path

        return None

    def _is_valid_metadata_file(self, metadata_path: Path) -> bool:
        """
        Check if a metadata file is valid YAML.

        Args:
            metadata_path: Path to the metadata file

        Returns:
            True if the file is valid YAML, False otherwise
        """
        try:
            with open(metadata_path, "r") as f:
                yaml.safe_load(f)
            return True
        except Exception:
            return False

    def infer(self, feature_name: Optional[str] = None) -> np.ndarray:
        """
        Perform inference for a single feature or all features.

        Args:
            feature_name: Optional name of the feature to retrieve.
                         If None, returns all features concatenated.

        Returns:
            Numpy array with the feature vector(s).

        Raises:
            ValueError: If feature_name is not found in metadata
        """
        if self._feature_provider is None:
            raise RuntimeError("Feature provider not initialized")

        if feature_name is not None:
            # Check if feature exists in metadata
            spec = next(
                (s for s in self._feature_provider._metadata if s.name == feature_name),
                None,
            )
            if spec is None:
                raise ValueError(
                    f"Feature '{feature_name}' not found in metadata. "
                    f"Available features: {[s.name for s in self._feature_provider._metadata]}"
                )

            # Get single feature by calling the method directly (bypassing validation)
            method_name = f"get_{feature_name}"
            method = getattr(self._feature_provider, method_name)
            feature = method()
            return self._handle_none_feature(feature, feature_name)
        else:
            # Get all features
            features_list = []
            for spec in self._feature_provider._metadata:
                # Get feature by calling the method directly (bypassing validation)
                method_name = f"get_{spec.name}"
                method = getattr(self._feature_provider, method_name)
                feature = method()
                feature = self._handle_none_feature(feature, spec.name)
                features_list.append(feature)

            return np.concatenate(features_list)

    def _handle_none_feature(
        self, feature: Optional[np.ndarray], feature_name: str
    ) -> np.ndarray:
        """
        Handle None feature returns with zero-padding.

        Args:
            feature: Feature vector (can be None)
            feature_name: Name of the feature (for metadata lookup)

        Returns:
            Feature vector with zero-padding if None
        """
        if feature is not None:
            return feature

        # Find the feature spec to get the expected dimension
        spec = next(
            (s for s in self._feature_provider._metadata if s.name == feature_name),
            None,
        )

        if spec is not None:
            # Zero-pad with correct dimension
            return np.zeros(spec.dim, dtype=np.float32)
        else:
            # Feature not found in metadata, return empty array
            return np.array([], dtype=np.float32)

    def list_available_models(self) -> List[dict]:
        """
        List all available models in search paths.

        Returns:
            List of dictionaries with model information (name, version, path)
        """
        return self._model_discoverer.list_available_models()
