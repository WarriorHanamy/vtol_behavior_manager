#!/usr/bin/env python3
"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Model Discovery Module

This module provides auto-discovery system to find and load ONNX models
from search paths in the neural_manager.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import yaml

METADATA_FILENAME = "observation_metadata.yaml"
ONNX_MODEL_FILENAME = "model.onnx"


@dataclass
class ModelMetadata:
  """
  Metadata for a machine learning model.

  Attributes:
      name: Name of the model
      version: Version of the model
      path: Path to the ONNX model file
      checksum: MD5 checksum of the model file
      input_shape: Shape of the model input tensor
      output_shape: Shape of the model output tensor
  """

  name: str
  version: str
  path: str
  checksum: Optional[str]
  input_shape: List[int]
  output_shape: List[int]


@dataclass
class DiscoveredModel:
  """
  Discovered model with its metadata.

  Attributes:
      metadata: Model metadata
      session: ONNX Runtime inference session
  """

  metadata: ModelMetadata
  session: Any


class ModelDiscoverer:
  """
  Auto-discovery system for ONNX models.

  This class provides:
  1. Configurable search paths for model discovery
  2. Multiple search strategies (task-specific and default)
  3. Automatic model and metadata loading
  4. Optional model integrity verification using MD5 checksums
  5. Listing of available models in search paths
  """

  def __init__(self, search_paths: List[Path | str]):
    """
    Initialize the model discoverer.

    Args:
        search_paths: List of directories to search for models
    """
    self._search_paths: List[Path] = [
      Path(p).expanduser().resolve() if isinstance(p, str) else p
      for p in search_paths
    ]

  def _find_metadata_file(self, task: Optional[str] = None) -> Optional[Path]:
    """
    Find metadata file using multiple search strategies.

    Search strategies:
    1. Task-specific: Look in task_name/observation_metadata.yaml
    2. Default: Look in search_path/observation_metadata.yaml

    Args:
        task: Optional task name for task-specific search

    Returns:
        Path to metadata file if found, None otherwise
    """
    for search_path in self._search_paths:
      if task is not None:
        task_specific_path = search_path / task / METADATA_FILENAME
        if task_specific_path.exists():
          try:
            with open(task_specific_path, "r") as f:
              yaml.safe_load(f)
            return task_specific_path
          except Exception:
            pass

      default_path = search_path / METADATA_FILENAME
      if default_path.exists():
        try:
          with open(default_path, "r") as f:
            yaml.safe_load(f)
          return default_path
        except Exception:
          pass

    return None

  def _load_metadata(self, metadata_path: Path) -> ModelMetadata:
    """
    Load metadata from YAML file.

    Args:
        metadata_path: Path to the metadata file

    Returns:
        ModelMetadata object
    """
    with open(metadata_path, "r") as f:
      data = yaml.safe_load(f)

    return ModelMetadata(
      name=data["name"],
      version=data["version"],
      path=data["path"],
      checksum=data.get("checksum"),
      input_shape=list(data["input_shape"]),
      output_shape=list(data["output_shape"]),
    )

  def _verify_checksum(self, model_file: Path, metadata: ModelMetadata) -> bool:
    """
    Verify model integrity using MD5 checksum.

    Args:
        model_file: Path to the model file
        metadata: Model metadata with checksum

    Returns:
        True if verification passes or checksum is not available

    Raises:
        ValueError: If checksums don't match
    """
    if metadata.checksum is None:
      return True

    calculated_checksum = calculate_md5_checksum(model_file)

    if calculated_checksum != metadata.checksum:
      raise ValueError(
        f"Checksum mismatch for {model_file}: "
        f"expected {metadata.checksum}, got {calculated_checksum}"
      )

    return True

  def discover_and_load(self, model_name: Optional[str] = None) -> DiscoveredModel:
    """
    Auto-discover and load a model.

    Args:
        model_name: Optional model/task name for task-specific search

    Returns:
        DiscoveredModel object with metadata and inference session

    Raises:
        FileNotFoundError: If metadata or model file not found
        ValueError: If checksum verification fails
    """
    metadata_path = self._find_metadata_file(model_name)
    if metadata_path is None:
      raise FileNotFoundError(
        f"Metadata file not found for model '{model_name}' in search paths: {self._search_paths}"
      )

    metadata = self._load_metadata(metadata_path)

    model_dir = metadata_path.parent
    model_file = model_dir / metadata.path

    if not model_file.exists():
      raise FileNotFoundError(
        f"Model file not found: {model_file} (from metadata: {metadata_path})"
      )

    self._verify_checksum(model_file, metadata)

    try:
      import onnxruntime as ort
      session = ort.InferenceSession(str(model_file))
    except ImportError:
      raise ImportError(
        "ONNX Runtime is required to load models. "
        "Install with: pip install onnxruntime"
      )
    except Exception as e:
      raise RuntimeError(f"Failed to load ONNX model from {model_file}: {str(e)}")

    return DiscoveredModel(metadata=metadata, session=session)

  def list_available_models(self) -> List[dict[str, Any]]:
    """
    List all available models in search paths.

    Returns:
        List of dictionaries with model information (name, version, path)
    """
    models = []
    seen_names = set()

    for search_path in self._search_paths:
      metadata_file = search_path / METADATA_FILENAME

      if metadata_file.exists():
        try:
          metadata = self._load_metadata(metadata_file)

          if metadata.name not in seen_names:
            models.append(
              {
                "name": metadata.name,
                "version": metadata.version,
                "path": metadata_file,
              }
            )
            seen_names.add(metadata.name)
        except Exception:
          pass

      for task_dir in search_path.iterdir():
        if task_dir.is_dir():
          task_metadata_file = task_dir / METADATA_FILENAME
          if task_metadata_file.exists():
            try:
              metadata = self._load_metadata(task_metadata_file)

              if metadata.name not in seen_names:
                models.append(
                  {
                    "name": metadata.name,
                    "version": metadata.version,
                    "path": task_metadata_file,
                  }
                )
                seen_names.add(metadata.name)
            except Exception:
              pass

    return models


def calculate_md5_checksum(file_path: Path) -> str:
  """
  Calculate MD5 checksum of a file.

  Args:
      file_path: Path to the file to calculate checksum for

  Returns:
      MD5 checksum as a hexadecimal string

  Raises:
      FileNotFoundError: If the file does not exist
  """
  if not file_path.exists():
    raise FileNotFoundError(f"File not found: {file_path}")

  md5_hash = hashlib.md5()
  with open(file_path, "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
      md5_hash.update(chunk)

  return md5_hash.hexdigest()
