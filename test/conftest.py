"""Shared test fixtures for deploy-side tests."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import yaml

# Add src to path so we can import neural_manager modules
DEPLOY_SIDE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(DEPLOY_SIDE_ROOT / "src"))
sys.path.insert(0, str(DEPLOY_SIDE_ROOT / "src" / "neural_inference"))

# Detect if real ROS2 message packages are available.
# After `make test-install`, goal_msgs and px4_msgs Python packages
# are copied from Docker to host site-packages.
ROS2_AVAILABLE = False
try:
  from goal_msgs.msg import GoalAcro  # noqa: F401
  from px4_msgs.msg import VehicleOdometry  # noqa: F401

  ROS2_AVAILABLE = True
except (ImportError, AttributeError, ModuleNotFoundError):
  pass

# Mock ROS2 modules when not available (host without colcon-built packages)
if not ROS2_AVAILABLE:
  _MOCKED_MODULES = [
    "rclpy",
    "rclpy.node",
    "rclpy.qos",
    "goal_msgs",
    "goal_msgs.msg",
    "px4_msgs",
    "px4_msgs.msg",
  ]

  for mod_name in _MOCKED_MODULES:
    if mod_name not in sys.modules or isinstance(sys.modules[mod_name], MagicMock):
      sys.modules[mod_name] = MagicMock()

  # Set message class attributes so `from goal_msgs.msg import GoalAcro` works
  sys.modules["rclpy.qos"].qos_profile_sensor_data = 1
  sys.modules["goal_msgs.msg"].GoalAcro = MagicMock
  sys.modules["goal_msgs.msg"].GoalHover = MagicMock
  sys.modules["goal_msgs.msg"].NeuralTarget = MagicMock
  sys.modules["px4_msgs.msg"].VehicleOdometry = MagicMock
  sys.modules["px4_msgs.msg"].TrajectorySetpoint = MagicMock
  sys.modules["px4_msgs.msg"].VehicleAccRatesSetpoint = MagicMock


@pytest.fixture
def identity_quat():
  """Identity quaternion [w, x, y, z] — no rotation."""
  return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)


@pytest.fixture
def tmp_metadata(tmp_path):
  """Factory for creating temporary observations_metadata.yaml files."""

  def _create(features: list[dict[str, int]]) -> Path:
    metadata = {"low_dim": features}
    path = tmp_path / "observations_metadata.yaml"
    with open(path, "w") as f:
      yaml.dump(metadata, f)
    return path

  return _create


@pytest.fixture
def tmp_action_metadata(tmp_path):
  """Factory for creating temporary action_metadata.yaml files."""

  def _create(
    max_ang_vel: list[float] = [3.0, 3.0, 1.0],
    min_thrust: float = 0.0,
    max_thrust: float = 2.0,
  ) -> Path:
    metadata = {
      "max_ang_vel": max_ang_vel,
      "min_thrust": min_thrust,
      "max_thrust": max_thrust,
    }
    path = tmp_path / "action_metadata.yaml"
    with open(path, "w") as f:
      yaml.dump(metadata, f)
    return tmp_path

  return _create


@pytest.fixture
def mock_acro_provider(tmp_metadata):
  """Create a VtolAcroFeatureProvider with mock metadata, no ROS2."""
  from neural_manager.neural_inference.features.vtol_acro_feature_provider import (
    VtolAcroFeatureProvider,
  )

  metadata_path = tmp_metadata(
    [
      {"name": "gate_layout", "dim": 2},
      {"name": "gate_pose", "dim": 6},
      {"name": "flu_vel", "dim": 3},
      {"name": "flu_ang_vel", "dim": 3},
      {"name": "last_raw_action", "dim": 4},
    ]
  )

  provider = VtolAcroFeatureProvider.__new__(VtolAcroFeatureProvider)
  provider._metadata_path = metadata_path

  # Set buffers BEFORE loading metadata (validation calls get_* methods)
  provider._ned_position = np.zeros(3, dtype=np.float32)
  provider._ned_velocity = np.zeros(3, dtype=np.float32)
  provider._ned_quat_frd = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
  provider._frd_ang_vel = np.zeros(3, dtype=np.float32)
  provider._gate_center = np.zeros(3, dtype=np.float32)
  provider._semi_major = 0.3
  provider._semi_short = 0.2
  provider._last_action = np.zeros(4, dtype=np.float32)

  # Now load and validate
  provider._metadata = provider._load_metadata()
  provider._validation_results = provider._validate_implementations()
  provider._print_validation_report(provider._validation_results)

  return provider


@pytest.fixture
def mock_hover_provider(tmp_metadata):
  """Create a VtolHoverFeatureProvider with mock metadata, no ROS2."""
  from neural_manager.neural_inference.features.vtol_hover_feature_provider import (
    VtolHoverFeatureProvider,
  )

  metadata_path = tmp_metadata(
    [
      {"name": "enu_to_target", "dim": 3},
      {"name": "enu_quat_flu", "dim": 4},
      {"name": "flu_vel", "dim": 3},
      {"name": "last_raw_action", "dim": 4},
    ]
  )

  provider = VtolHoverFeatureProvider.__new__(VtolHoverFeatureProvider)
  provider._metadata_path = metadata_path

  # Set buffers BEFORE loading metadata
  provider._ned_position = np.zeros(3, dtype=np.float32)
  provider._ned_velocity = np.zeros(3, dtype=np.float32)
  provider._ned_quat_frd = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
  provider._frd_ang_vel = np.zeros(3, dtype=np.float32)
  provider._ned_target_position = np.zeros(3, dtype=np.float32)
  provider._last_action = np.zeros(4, dtype=np.float32)

  # Now load and validate
  provider._metadata = provider._load_metadata()
  provider._validation_results = provider._validate_implementations()
  provider._print_validation_report(provider._validation_results)

  return provider
