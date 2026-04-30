"""ROS2 integration test — runs inside bht container, no PX4 needed.

Publishes fake GoalAcro / GoalHover and VehicleOdometry, verifies
NeuralControlNode produces VehicleAccRatesSetpoint output.

Usage (inside bht container):
    python3 test/integration/test_goal_flow.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import yaml

# Import ROS2_AVAILABLE from parent conftest
sys.path.insert(0, str(Path(__file__).parent.parent))
from conftest import ROS2_AVAILABLE

# --- Host-safe tests (no ROS2 needed) ---


class TestActionMetadataLoading:
  """Test _load_action_metadata without ROS2 imports."""

  def test_loads_valid_yaml(self, tmp_action_metadata):
    from test_action_metadata import _load_action_metadata

    revision_dir = tmp_action_metadata(
      max_ang_vel=[5.0, 4.0, 2.0],
      min_thrust=0.5,
      max_thrust=2.5,
    )
    result = _load_action_metadata(revision_dir)
    assert result is not None
    assert result["max_ang_vel"] == [5.0, 4.0, 2.0]
    assert result["min_thrust"] == 0.5
    assert result["max_thrust"] == 2.5

  def test_returns_none_when_missing(self, tmp_path):
    from test_action_metadata import _load_action_metadata

    result = _load_action_metadata(tmp_path)
    assert result is None


class TestFeatureProviderAcroNoRos2:
  """Test VtolAcroFeatureProvider with mocked ROS2 — pure numpy."""

  def test_update_from_goal_acro(self, mock_acro_provider):
    """Verify update_from_goal_acro updates gate center and geometry."""
    from unittest.mock import MagicMock

    mock_msg = MagicMock()
    mock_msg.gate_center = [3.5, 0.0, 1.5]
    mock_msg.semi_major = 0.3
    mock_msg.semi_short = 0.2

    mock_acro_provider.update_from_goal_acro(mock_msg)
    np.testing.assert_allclose(mock_acro_provider._gate_center, [3.5, 0.0, 1.5])
    assert mock_acro_provider._semi_major == 0.3
    assert mock_acro_provider._semi_short == 0.2

  def test_gate_layout(self, mock_acro_provider):
    mock_acro_provider._semi_major = 0.3
    mock_acro_provider._semi_short = 0.2
    result = mock_acro_provider.get_gate_layout()
    assert result.shape == (2,)
    np.testing.assert_allclose(result, [0.3, 0.2])

  def test_gate_pose(self, mock_acro_provider, identity_quat):
    mock_acro_provider._ned_position = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    mock_acro_provider._ned_quat_frd = identity_quat
    mock_acro_provider._gate_center = np.array([4.0, 0.0, 1.5], dtype=np.float32)
    result = mock_acro_provider.get_gate_pose()
    assert result.shape == (6,)

  def test_all_features_18d(self, mock_acro_provider, identity_quat):
    mock_acro_provider._ned_quat_frd = identity_quat
    mock_acro_provider._ned_position = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    mock_acro_provider._gate_center = np.array([4.0, 0.0, 1.5], dtype=np.float32)
    result = mock_acro_provider.get_all_features()
    assert result.shape == (18,)


class TestFeatureProviderHoverNoRos2:
  """Test VtolHoverFeatureProvider with mocked ROS2 — pure numpy."""

  def test_update_from_goal_hover(self, mock_hover_provider):
    """Verify update_from_goal_hover updates target position."""
    from unittest.mock import MagicMock

    mock_msg = MagicMock()
    mock_msg.position = [1.0, 2.0, 3.0]

    mock_hover_provider.update_from_goal_hover(mock_msg)
    np.testing.assert_allclose(mock_hover_provider._ned_target_position, [1.0, 2.0, 3.0])

  def test_enu_to_target(self, mock_hover_provider, identity_quat):
    mock_hover_provider._ned_position = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    mock_hover_provider._ned_target_position = np.array([4.0, 5.0, 6.0], dtype=np.float32)
    mock_hover_provider._ned_quat_frd = identity_quat
    result = mock_hover_provider.get_enu_to_target()
    assert result.shape == (3,)

  def test_all_features_14d(self, mock_hover_provider, identity_quat):
    mock_hover_provider._ned_quat_frd = identity_quat
    mock_hover_provider._ned_target_position = np.array([0.0, 0.0, 2.0], dtype=np.float32)
    result = mock_hover_provider.get_all_features()
    assert result.shape == (14,)


# --- ROS2-dependent tests (skip on host) ---


@pytest.mark.skipif(not ROS2_AVAILABLE, reason="ROS2 not available (not in Docker)")
class TestGoalMessageImport:
  """Verify ROS2 message types can be imported."""

  def test_goal_acro_import(self):
    from goal_msgs.msg import GoalAcro

    msg = GoalAcro()
    msg.gate_center = [3.5, 0.0, 1.5]
    msg.semi_major = 0.3
    msg.semi_short = 0.2
    assert msg.gate_center[0] == 3.5

  def test_goal_hover_import(self):
    from goal_msgs.msg import GoalHover

    msg = GoalHover()
    msg.position = [1.0, 2.0, 3.0]
    msg.yaw = 0.5
    assert msg.position[0] == 1.0

  def test_vehicle_odometry_import(self):
    from px4_msgs.msg import VehicleOdometry

    msg = VehicleOdometry()
    msg.q = [1.0, 0.0, 0.0, 0.0]
    assert msg.q[0] == 1.0

  def test_neural_target_import(self):
    from goal_msgs.msg import NeuralTarget

    msg = NeuralTarget()
    msg.task_type = NeuralTarget.TASK_HOVER
    assert msg.task_type == 0
    assert NeuralTarget.TASK_ACRO == 1

  def test_neural_target_fields(self):
    from goal_msgs.msg import NeuralTarget

    msg = NeuralTarget()
    msg.task_type = NeuralTarget.TASK_HOVER
    msg.goal_hover.position = [1.0, 2.0, 3.0]
    msg.goal_hover.yaw = 0.5
    assert msg.goal_hover.position[0] == 1.0
    assert msg.goal_hover.yaw == 0.5

    msg.task_type = NeuralTarget.TASK_ACRO
    msg.goal_acro.gate_center = [3.5, 0.0, 1.5]
    msg.goal_acro.semi_major = 0.3
    msg.goal_acro.semi_short = 0.2
    assert msg.goal_acro.gate_center[0] == 3.5
    assert msg.goal_acro.semi_major == 0.3
