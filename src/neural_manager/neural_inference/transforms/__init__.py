"""
Transform utilities for neural inference.

This module provides stateless pure functions for coordinate transformations
and data encoding used in neural network observation preparation.

Modules:
- math_utils: Low-level math operations (quaternions, rotations)
- transform_registry: Registry system for transforms
- coordinate: Coordinate transformation functions (ned_to_frd, frd_to_flu)
- encoding: Encoding functions (quat_to_yaw, angle_to_sincos)
"""

from .math_utils import (
    quaternion_to_euler,
    quaternion_to_yaw,
    euler_to_quaternion,
    rotation_matrix_ned_to_body,
    rotation_matrix_body_to_ned,
    quaternion_multiply,
    quat_act_rot,
    quat_pas_rot,
    quat_right_multiply_flu_frd,
    frd_flu_rotate,
    normalize_quaternion,
    quaternion_to_rotation_matrix,
    rotation_matrix_to_quaternion,
)

from .transform_registry import (
    register_transform,
    get_transform,
    has_transform,
    list_transforms,
    apply_transform,
    apply_transform_chain,
)

# Import coordinate and encoding modules to trigger registration
from . import coordinate
from . import encoding

__all__ = [
    # Math utils
    "quaternion_to_euler",
    "quaternion_to_yaw",
    "euler_to_quaternion",
    "rotation_matrix_ned_to_body",
    "rotation_matrix_body_to_ned",
    "quaternion_multiply",
    "quat_act_rot",
    "quat_pas_rot",
    "quat_right_multiply_flu_frd",
    "frd_flu_rotate",
    "normalize_quaternion",
    "quaternion_to_rotation_matrix",
    "rotation_matrix_to_quaternion",
    # Transform registry
    "register_transform",
    "get_transform",
    "has_transform",
    "list_transforms",
    "apply_transform",
    "apply_transform_chain",
    # Modules
    "coordinate",
    "encoding",
]
