"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Math utilities for coordinate transformations.
"""

import numpy as np


def quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
  """Multiply two Hamilton quaternions in [w, x, y, z] order.

  Args:
      q1: First quaternion [w, x, y, z]
      q2: Second quaternion [w, x, y, z]

  Returns:
      Product quaternion q1 * q2 in [w, x, y, z] order

  """
  w1, x1, y1, z1 = q1
  w2, x2, y2, z2 = q2
  return np.array(
    [
      w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
      w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
      w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
      w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ],
    dtype=np.result_type(q1.dtype, q2.dtype),
  )


def quat_conjugate(quat: np.ndarray) -> np.ndarray:
  """Compute quaternion conjugate in [w, x, y, z] order.

  Args:
      quat: Quaternion [w, x, y, z]

  Returns:
      Quaternion conjugate [w, -x, -y, -z]

  """
  return np.array([quat[0], -quat[1], -quat[2], -quat[3]], dtype=quat.dtype)


def quat_rotate(quat: np.ndarray, vec: np.ndarray) -> np.ndarray:
  """Actively rotate a 3D vector with a Hamilton quaternion.

  Args:
      quat: Rotation quaternion [w, x, y, z]
      vec: 3D vector to rotate

  Returns:
      Rotated 3D vector

  """
  dtype = np.result_type(quat.dtype, vec.dtype)
  q = quat.astype(dtype)
  v = vec.astype(dtype)

  w = q[0]
  u = q[1:4]
  uv = np.cross(u, v)
  uuv = np.cross(u, uv)
  return v + 2.0 * (w * uv + uuv)


def canonicalize_quat_w_positive(quat: np.ndarray) -> np.ndarray:
  """Canonicalize quaternion sign so the scalar term is non-negative.

  Args:
      quat: Quaternion [w, x, y, z]

  Returns:
      Equivalent quaternion with w >= 0

  """
  return -quat if quat[0] < 0.0 else quat.copy()


def ned_to_frd_rotate(ned_quat_frd: np.ndarray, vec: np.ndarray) -> np.ndarray:
  """Convert a world-frame NED vector into a body-frame FRD vector.

  The input quaternion follows the repository convention used by PX4:
  it represents body orientation in NED-FRD form. Converting a vector from the
  NED world frame into the FRD body frame therefore uses the inverse rotation.

  Args:
      ned_quat_frd: Quaternion in NED-FRD [w, x, y, z]
      vec: Vector expressed in NED frame [n, e, d]

  Returns:
      Vector expressed in FRD frame [x, y, z]

  """
  return quat_rotate(quat_conjugate(ned_quat_frd), vec)


def ned_enu_rotate(vec: np.ndarray) -> np.ndarray:
  """Convert vector from NED (North-East-Down) to ENU (East-North-Up) frame.

  NED: x=north, y=east, z=down
  ENU: x=east, y=north, z=up

  Args:
      vec: Vector in NED frame [n, e, d]

  Returns:
      Vector in ENU frame [e, n, -d]

  """
  return np.array([vec[1], vec[0], -vec[2]], dtype=vec.dtype)


def ned_quat_frd_to_enu_quat_flu(ned_quat_frd: np.ndarray) -> np.ndarray:
  """Transform a quaternion from NED-FRD to ENU-FLU.

  The input quaternion is assumed to represent orientation between the world frame
  and the body frame, with vectors actively rotated from NED world to FRD body.

  Args:
      ned_quat_frd: Quaternion in NED-FRD [w, x, y, z]

  Returns:
      Quaternion in ENU-FLU [w, x, y, z]

  """
  dtype = np.result_type(ned_quat_frd.dtype, np.float32)
  sqrt_half = np.sqrt(np.array(0.5, dtype=dtype))

  q_frd_to_flu = np.array([0.0, 1.0, 0.0, 0.0], dtype=dtype)
  q_enu_to_ned = np.array([0.0, sqrt_half, sqrt_half, 0.0], dtype=dtype)

  enu_quat_flu = quat_multiply(
    q_enu_to_ned, quat_multiply(ned_quat_frd.astype(dtype), q_frd_to_flu)
  )
  return canonicalize_quat_w_positive(enu_quat_flu)


def frd_flu_rotate(vec: np.ndarray) -> np.ndarray:
  """Convert vector from FLU (Forward-Left-Up) to FRD (Forward-Right-Down) frame.

  FLU: x=forward, y=left, z=up
  FRD: x=forward, y=right, z=down

  Args:
      vec: Vector in FLU frame [x, y, z]

  Returns:
      Vector in FRD frame [x, -y, -z]

  """
  return np.array([vec[0], -vec[1], -vec[2]], dtype=vec.dtype)
