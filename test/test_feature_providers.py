"""Tests for feature providers — no ROS2 required."""

import numpy as np
import pytest


class TestVtolAcroFeatureProvider:
  """Test VtolAcroFeatureProvider feature computation with mocked buffers."""

  def test_gate_layout_returns_2d(self, mock_acro_provider):
    mock_acro_provider._semi_major = 0.3
    mock_acro_provider._semi_short = 0.2
    result = mock_acro_provider.get_gate_layout()
    assert result.shape == (2,)
    np.testing.assert_allclose(result, [0.3, 0.2])

  def test_gate_pose_identity_quat(self, mock_acro_provider, identity_quat):
    mock_acro_provider._ned_position = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    mock_acro_provider._ned_quat_frd = identity_quat
    mock_acro_provider._gate_center = np.array([4.0, 0.0, 1.5], dtype=np.float32)

    result = mock_acro_provider.get_gate_pose()
    assert result.shape == (6,)

    # Identity quat: NED→FRD is identity, FRD→FLU flips Y,Z
    # rel_ned = [4,0,1.5] - [1,0,0] = [3, 0, 1.5]
    # rel_frd = [3, 0, 1.5] (identity rotation)
    # rel_flu = [3, 0, -1.5] (FRD→FLU: y→-y, z→-z)
    np.testing.assert_allclose(result[:3], [3.0, 0.0, -1.5], atol=1e-5)

  def test_gate_pose_normal_with_identity(self, mock_acro_provider, identity_quat):
    mock_acro_provider._ned_quat_frd = identity_quat
    result = mock_acro_provider.get_gate_pose()

    # Gate normal = NED north [1,0,0], identity quat
    # normal_frd = [1,0,0] (identity)
    # normal_flu = [1,0,0] (x unchanged in frd_flu_rotate)
    np.testing.assert_allclose(result[3:], [1.0, 0.0, 0.0], atol=1e-5)

  def test_flu_vel_identity_quat(self, mock_acro_provider, identity_quat):
    mock_acro_provider._ned_quat_frd = identity_quat
    mock_acro_provider._ned_velocity = np.array([1.0, 2.0, 3.0], dtype=np.float32)

    result = mock_acro_provider.get_flu_vel()
    assert result.shape == (3,)
    # NED vel [1,2,3] → FRD (identity) [1,2,3] → FLU [1,-2,-3]
    np.testing.assert_allclose(result, [1.0, -2.0, -3.0], atol=1e-5)

  def test_flu_ang_vel_identity_quat(self, mock_acro_provider, identity_quat):
    mock_acro_provider._ned_quat_frd = identity_quat
    mock_acro_provider._frd_ang_vel = np.array([0.1, 0.2, 0.3], dtype=np.float32)

    result = mock_acro_provider.get_flu_ang_vel()
    assert result.shape == (3,)
    # FRD→FLU: y→-y, z→-z
    np.testing.assert_allclose(result, [0.1, -0.2, -0.3], atol=1e-5)

  def test_last_raw_action(self, mock_acro_provider):
    action = np.array([0.5, -0.3, 0.1, 0.8], dtype=np.float32)
    mock_acro_provider.update_last_action(action)
    result = mock_acro_provider.get_last_raw_action()
    np.testing.assert_array_equal(result, action)

  def test_all_features_concatenated_dim(self, mock_acro_provider, identity_quat):
    mock_acro_provider._ned_quat_frd = identity_quat
    mock_acro_provider._ned_position = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    mock_acro_provider._gate_center = np.array([4.0, 0.0, 1.5], dtype=np.float32)

    result = mock_acro_provider.get_all_features()
    # 2 + 6 + 3 + 3 + 4 = 18
    assert result.shape == (18,)


class TestVtolHoverFeatureProvider:
  """Test VtolHoverFeatureProvider feature computation with mocked buffers."""

  def test_enu_to_target_identity_quat(self, mock_hover_provider, identity_quat):
    mock_hover_provider._ned_position = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    mock_hover_provider._ned_target_position = np.array([4.0, 5.0, 6.0], dtype=np.float32)
    mock_hover_provider._ned_quat_frd = identity_quat

    result = mock_hover_provider.get_enu_to_target()
    assert result.shape == (3,)
    # ned_error = [3, 3, 3]
    # ned_enu: [e, n, -d] = [3, 3, -3]
    np.testing.assert_allclose(result, [3.0, 3.0, -3.0], atol=1e-5)

  def test_enu_quat_flu_identity(self, mock_hover_provider, identity_quat):
    mock_hover_provider._ned_quat_frd = identity_quat
    result = mock_hover_provider.get_enu_quat_flu()
    assert result.shape == (4,)
    # Should be canonicalized (w >= 0)
    assert result[0] >= 0.0

  def test_flu_vel(self, mock_hover_provider, identity_quat):
    mock_hover_provider._ned_quat_frd = identity_quat
    mock_hover_provider._ned_velocity = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    result = mock_hover_provider.get_flu_vel()
    assert result.shape == (3,)

  def test_all_features_concatenated_dim(self, mock_hover_provider, identity_quat):
    mock_hover_provider._ned_quat_frd = identity_quat
    mock_hover_provider._ned_target_position = np.array([0.0, 0.0, 2.0], dtype=np.float32)

    result = mock_hover_provider.get_all_features()
    # 3 + 4 + 3 + 4 = 14
    assert result.shape == (14,)
