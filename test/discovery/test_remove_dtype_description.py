"""
Test for removal of dtype and description references (FR-2).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import ast

import pytest


def test_feature_provider_base_no_dtype_or_description():
    """Test that feature_provider_base.py has no dtype or description references."""
    with open(
        Path(__file__).parent.parent.parent
        / "src"
        / "features"
        / "feature_provider_base.py",
    ) as f:
        content = f.read()

    # Parse the file as AST
    tree = ast.parse(content)

    # Check for any string references to "dtype" or "description"
    # in code (excluding docstrings and comments)
    dtype_refs = []
    description_refs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id == "dtype":
                dtype_refs.append(node.lineno)
            if node.id == "description":
                description_refs.append(node.lineno)

    # Should have no dtype references
    assert len(dtype_refs) == 0, (
        f"Found {len(dtype_refs)} dtype references at lines: {dtype_refs}"
    )

    # Should have no description references
    assert len(description_refs) == 0, (
        f"Found {len(description_refs)} description references at lines: {description_refs}"
    )


def test_model_schema_no_dtype_or_description():
    """Test that model_schema.py has no dtype or description references."""
    with open(
        Path(__file__).parent.parent.parent
        / "src"
        / "neural_manager"
        / "neural_inference"
        / "schemas"
        / "model_schema.py",
    ) as f:
        content = f.read()

    # Parse the file as AST
    tree = ast.parse(content)

    # Check for any string references to "dtype" or "description"
    dtype_refs = []
    description_refs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id == "dtype":
                dtype_refs.append(node.lineno)
            if node.id == "description":
                description_refs.append(node.lineno)

    # Should have no dtype references
    assert len(dtype_refs) == 0, (
        f"Found {len(dtype_refs)} dtype references at lines: {dtype_refs}"
    )

    # Should have no description references
    assert len(description_refs) == 0, (
        f"Found {len(description_refs)} description references at lines: {description_refs}"
    )
