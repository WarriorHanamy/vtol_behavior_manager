"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Transform Registry Module

This module provides a registry system for coordinate transformations
and encoding functions used in neural network inference.

Main features:
1. Decorator-based transform registration
2. Transform lookup and execution
3. Transform chain application
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List


_TRANSFORM_REGISTRY: Dict[str, Callable] = {}


def register_transform(name: str) -> Callable[[Callable], Callable]:
    """
    Decorator to register a transform function with a given name.

    Args:
        name: The name to register the transform under.

    Returns:
        A decorator function that registers the transform and returns it unchanged.

    Example:
        @register_transform("ned_to_frd")
        def ned_to_frd(quat, vec):
            ...
    """

    def decorator(func: Callable) -> Callable:
        _TRANSFORM_REGISTRY[name] = func
        return func

    return decorator


def get_transform(name: str) -> Callable:
    """
    Get a registered transform function by name.

    Args:
        name: The name of the registered transform.

    Returns:
        The registered transform function.

    Raises:
        KeyError: If no transform is registered with the given name.
    """
    if name not in _TRANSFORM_REGISTRY:
        raise KeyError(
            f"Transform '{name}' not found in registry. "
            f"Available transforms: {list_transforms()}"
        )
    return _TRANSFORM_REGISTRY[name]


def has_transform(name: str) -> bool:
    """
    Check if a transform is registered with the given name.

    Args:
        name: The name of the transform to check.

    Returns:
        True if the transform is registered, False otherwise.
    """
    return name in _TRANSFORM_REGISTRY


def list_transforms() -> List[str]:
    """
    List all registered transform names.

    Returns:
        A sorted list of all registered transform names.
    """
    return sorted(_TRANSFORM_REGISTRY.keys())


def apply_transform(name: str, *args: Any, **kwargs: Any) -> Any:
    """
    Apply a registered transform with the given arguments.

    Args:
        name: The name of the registered transform.
        *args: Positional arguments to pass to the transform.
        **kwargs: Keyword arguments to pass to the transform.

    Returns:
        The result of applying the transform.

    Raises:
        KeyError: If no transform is registered with the given name.
    """
    transform = get_transform(name)
    return transform(*args, **kwargs)


def apply_transform_chain(
    transforms: List[str], initial_value: Any, **context: Any
) -> Any:
    """
    Apply a chain of transforms sequentially.

    Each transform receives the output of the previous transform as its first
    positional argument, along with any additional context as keyword arguments.

    Args:
        transforms: List of transform names to apply in sequence.
        initial_value: The initial value to pass to the first transform.
        **context: Additional keyword arguments passed to all transforms.

    Returns:
        The result of applying all transforms in sequence.

    Raises:
        KeyError: If any transform is not registered.

    Example:
        result = apply_transform_chain(
            ["ned_to_frd", "frd_to_flu"],
            initial_value=vector,
            quat=quaternion
        )
    """
    result = initial_value
    for transform_name in transforms:
        transform = get_transform(transform_name)
        result = transform(result, **context)
    return result
