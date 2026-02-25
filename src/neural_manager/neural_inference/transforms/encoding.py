"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Encoding Transformation Module

This module provides encoding transformation functions registered
in the transform registry.

Transforms:
- quat_to_yaw: Extract yaw angle from quaternion
- angle_to_sincos: Convert angle to sin/cos encoding
"""

from __future__ import annotations

import math

import numpy as np

from .transform_registry import register_transform
from .math_utils import quaternion_to_yaw


@register_transform("quat_to_yaw")
def quat_to_yaw(quat: np.ndarray) -> float:
    """
    Extract yaw angle from quaternion.

    Args:
        quat: Quaternion [w, x, y, z] in Hamilton convention.

    Returns:
        Yaw angle in radians.
    """
    return quaternion_to_yaw(quat)


@register_transform("angle_to_sincos")
def angle_to_sincos(angle: float) -> np.ndarray:
    """
    Convert an angle to sin/cos encoding.

    This encoding is commonly used in neural networks to handle
    angular periodicity without discontinuities.

    Args:
        angle: Angle in radians.

    Returns:
        numpy array [cos(angle), sin(angle)].
    """
    return np.array([math.cos(angle), math.sin(angle)])
