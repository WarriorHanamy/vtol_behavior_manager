"""
pytest configuration and fixtures for feature provider tests.
"""

import sys
from pathlib import Path
import tempfile
import pytest

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_observation_metadata():
    """Create a sample observation_metadata.yaml file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
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
""")
        return f.name


@pytest.fixture
def single_feature_metadata():
    """Create metadata with single feature"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
features:
  - name: target_error
    dim: 3
    dtype: float32
    description: "Position error vector in FLU body frame"
""")
        return f.name


@pytest.fixture
def metadata_missing_description():
    """Create metadata with missing optional description field"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
features:
  - name: target_error
    dim: 3
    dtype: float32
""")
        return f.name
