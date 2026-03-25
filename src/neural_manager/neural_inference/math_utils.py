"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Math utilities for coordinate transformations.
"""

import numpy as np


def frd_flu_rotate(vec: np.ndarray) -> np.ndarray:
  """
  Convert vector from FLU (Forward-Left-Up) to FRD (Forward-Right-Down) frame.

  FLU: x=forward, y=left, z=up
  FRD: x=forward, y=right, z=down

  Args:
      vec: Vector in FLU frame [x, y, z]

  Returns:
      Vector in FRD frame [x, -y, -z]
  """
  return np.array([vec[0], -vec[1], -vec[2]], dtype=vec.dtype)
