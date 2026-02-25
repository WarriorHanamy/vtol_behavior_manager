"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Fixtures for feature provider tests
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent / "src"
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_observation_metadata(tmp_path):
    """Create a sample observation_metadata.yaml file"""
    metadata_path = tmp_path / "observation_metadata.yaml"
    metadata_content = """
features:
  - name: target_error
    dim: 3
    dtype: float32
    description: "Position error vector in FLU body frame"
  - name: gravity_projection
    dim: 3
    dtype: float32
    description: "Gravity vector in FLU body frame"
  - name: angular_velocity
    dim: 3
    dtype: float32
    description: "Angular velocity in FLU body frame"
  - name: current_yaw_encoding
    dim: 2
    dtype: float32
    description: "Sin/cos encoding of current yaw angle"
  - name: target_pos_body
    dim: 3
    dtype: float32
    description: "Target position in FLU body frame"
  - name: target_yaw_encoding
    dim: 2
    dtype: float32
    description: "Sin/cos encoding of target yaw angle"
  - name: last_action
    dim: 4
    dtype: float32
    description: "Previous action vector"
"""
    metadata_path.write_text(metadata_content)
    return metadata_path


@pytest.fixture
def single_feature_metadata(tmp_path):
    """Create metadata with single feature"""
    metadata_path = tmp_path / "observation_metadata.yaml"
    metadata_content = """
features:
  - name: target_error
    dim: 3
    dtype: float32
    description: "Position error vector in FLU body frame"
"""
    metadata_path.write_text(metadata_content)
    return metadata_path


@pytest.fixture
def metadata_missing_description(tmp_path):
    """Create metadata with missing optional description field"""
    metadata_path = tmp_path / "observation_metadata.yaml"
    metadata_content = """
features:
  - name: target_error
    dim: 3
    dtype: float32
"""
    metadata_path.write_text(metadata_content)
    return metadata_path
