"""Tests for math_utils coordinate transformations."""

import numpy as np
import pytest
from neural_manager.neural_inference.math_utils import (
  canonicalize_quat_w_positive,
  frd_flu_rotate,
  ned_enu_rotate,
  ned_quat_frd_to_enu_quat_flu,
  ned_to_frd_rotate,
  quat_conjugate,
  quat_multiply,
  quat_rotate,
)

# --- quat_conjugate ---


class TestQuatConjugate:
  def test_identity(self):
    q = np.array([1.0, 0.0, 0.0, 0.0])
    result = quat_conjugate(q)
    np.testing.assert_array_equal(result, [1.0, 0.0, 0.0, 0.0])

  def test_pure_rotation(self):
    q = np.array([0.0, 1.0, 0.0, 0.0])
    result = quat_conjugate(q)
    np.testing.assert_array_equal(result, [0.0, -1.0, 0.0, 0.0])

  def test_general(self):
    q = np.array([0.5, 0.5, 0.5, 0.5])
    result = quat_conjugate(q)
    np.testing.assert_array_equal(result, [0.5, -0.5, -0.5, -0.5])


# --- quat_multiply ---


class TestQuatMultiply:
  def test_identity(self):
    q = np.array([0.707, 0.0, 0.707, 0.0])
    identity = np.array([1.0, 0.0, 0.0, 0.0])
    result = quat_multiply(identity, q)
    np.testing.assert_allclose(result, q, atol=1e-5)

  def test_inverse(self):
    # Use a properly unit-length quaternion
    angle = np.pi / 3  # 60 degrees
    q = np.array([np.cos(angle / 2), 0.0, np.sin(angle / 2), 0.0])
    q_inv = quat_conjugate(q)
    result = quat_multiply(q, q_inv)
    np.testing.assert_allclose(result, [1.0, 0.0, 0.0, 0.0], atol=1e-6)


# --- quat_rotate ---


class TestQuatRotate:
  def test_identity_rotation(self):
    q = np.array([1.0, 0.0, 0.0, 0.0])
    v = np.array([1.0, 2.0, 3.0])
    result = quat_rotate(q, v)
    np.testing.assert_allclose(result, v, atol=1e-6)

  def test_90_deg_yaw(self):
    # 90 degree rotation around Z axis: q = [cos(45), 0, 0, sin(45)]
    q = np.array([np.cos(np.pi / 4), 0.0, 0.0, np.sin(np.pi / 4)])
    v = np.array([1.0, 0.0, 0.0])  # forward
    result = quat_rotate(q, v)
    # Should rotate to left: [0, 1, 0]
    np.testing.assert_allclose(result, [0.0, 1.0, 0.0], atol=1e-6)

  def test_180_deg_roll(self):
    # 180 degree rotation around X axis
    q = np.array([0.0, 1.0, 0.0, 0.0])
    v = np.array([0.0, 1.0, 0.0])  # left
    result = quat_rotate(q, v)
    # Should flip Y and Z: [0, -1, 0]
    np.testing.assert_allclose(result, [0.0, -1.0, 0.0], atol=1e-6)


# --- canonicalize_quat_w_positive ---


class TestCanonicalize:
  def test_already_positive(self):
    q = np.array([0.5, 0.5, 0.5, 0.5])
    result = canonicalize_quat_w_positive(q)
    np.testing.assert_array_equal(result, q)

  def test_negative_w(self):
    q = np.array([-0.5, 0.5, 0.5, 0.5])
    result = canonicalize_quat_w_positive(q)
    np.testing.assert_array_equal(result, [0.5, -0.5, -0.5, -0.5])


# --- ned_to_frd_rotate ---


class TestNedToFrd:
  def test_identity_quat(self):
    q = np.array([1.0, 0.0, 0.0, 0.0])
    v_ned = np.array([1.0, 0.0, 0.0])  # north
    result = ned_to_frd_rotate(q, v_ned)
    # Identity: NED north = FRD forward
    np.testing.assert_allclose(result, [1.0, 0.0, 0.0], atol=1e-6)

  def test_90_deg_yaw(self):
    # Body rotated 90 deg yaw: FRD-X points NED-East
    q = np.array([np.cos(np.pi / 4), 0.0, 0.0, np.sin(np.pi / 4)])
    v_ned = np.array([0.0, 1.0, 0.0])  # east
    result = ned_to_frd_rotate(q, v_ned)
    # In body frame, east = forward
    np.testing.assert_allclose(result, [1.0, 0.0, 0.0], atol=1e-6)


# --- ned_enu_rotate ---


class TestNedEnu:
  def test_north_to_north(self):
    v_ned = np.array([1.0, 0.0, 0.0])  # north
    result = ned_enu_rotate(v_ned)
    # ENU: x=east, y=north, z=up
    np.testing.assert_allclose(result, [0.0, 1.0, 0.0], atol=1e-6)

  def test_down_to_up(self):
    v_ned = np.array([0.0, 0.0, 1.0])  # down
    result = ned_enu_rotate(v_ned)
    np.testing.assert_allclose(result, [0.0, 0.0, -1.0], atol=1e-6)


# --- frd_flu_rotate ---


class TestFrdFlu:
  def test_forward_unchanged(self):
    v = np.array([1.0, 0.0, 0.0])
    result = frd_flu_rotate(v)
    np.testing.assert_array_equal(result, [1.0, 0.0, 0.0])

  def test_y_z_flipped(self):
    v = np.array([0.0, 1.0, 2.0])
    result = frd_flu_rotate(v)
    np.testing.assert_array_equal(result, [0.0, -1.0, -2.0])


# --- ned_quat_frd_to_enu_quat_flu ---


class TestNedQuatFrdToEnuQuatFlu:
  def test_identity_quat(self):
    q = np.array([1.0, 0.0, 0.0, 0.0])
    result = ned_quat_frd_to_enu_quat_flu(q)
    # Identity should produce a valid quaternion
    norm = np.linalg.norm(result)
    np.testing.assert_allclose(norm, 1.0, atol=1e-5)
    # w should be >= 0 (canonicalized)
    assert result[0] >= 0.0

  def test_canonicalized(self):
    # Any quaternion should have w >= 0 after transform
    q = np.array([0.0, 0.707, 0.0, 0.707])
    result = ned_quat_frd_to_enu_quat_flu(q)
    assert result[0] >= 0.0
