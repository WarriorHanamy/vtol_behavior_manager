"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Coordinate Transformation Module

This module provides coordinate transformation functions registered
in the transform registry.

Transforms:
- ned_to_frd: NED (North-East-Down) to FRD (Forward-Right-Down)
- frd_to_flu: FRD (Forward-Right-Down) to FLU (Forward-Left-Up)
"""

from __future__ import annotations

import numpy as np

from .transform_registry import register_transform
from .math_utils import quat_act_rot, frd_flu_rotate


@register_transform("ned_to_frd")
def ned_to_frd(quat: np.ndarray, vec: np.ndarray) -> np.ndarray:
    """
    Transform a vector from NED frame to FRD body frame using quaternion.

    NED (North-East-Down) is the global reference frame.
    FRD (Forward-Right-Down) is the body frame aligned with aircraft.

    This uses active rotation: the vector is rotated, not the coordinate system.

    Args:
        quat: Quaternion [w, x, y, z] representing body orientation.
        vec: Vector in NED frame [vx, vy, vz].

    Returns:
        Vector in FRD body frame [vx, vy, vz].
    """
    return quat_act_rot(quat, vec)


@register_transform("frd_to_flu")
def frd_to_flu(vec: np.ndarray) -> np.ndarray:
    """
    Transform a vector from FRD frame to FLU frame.

    FRD (Forward-Right-Down) and FLU (Forward-Left-Up) are both body frames
    but with different axis conventions.

    This transformation rotates the Y and Z axes:
    - X (Forward) stays the same
    - Y: Right -> Left (negated)
    - Z: Down -> Up (negated)

    Args:
        vec: Vector in FRD frame [vx, vy, vz].

    Returns:
        Vector in FLU frame [vx, vy, vz].
    """
    return frd_flu_rotate(vec)
