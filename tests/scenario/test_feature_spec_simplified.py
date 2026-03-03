"""
Test for FeatureSpec simplified structure (FR-1).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from dataclasses import fields

from features.feature_provider_base import FeatureSpec as BaseFeatureSpec
from neural_manager.neural_inference.schemas.model_schema import (
    FeatureSpec as ModelFeatureSpec,
)


class TestFeatureSpecSimplified:
    """Test that FeatureSpec contains only name and dim fields."""

    def test_feature_spec_base_has_only_name_and_dim(self):
        """Test that base FeatureSpec has only name and dim fields."""
        feature_spec = BaseFeatureSpec(name="test_feature", dim=10)

        # Verify instance was created successfully
        assert feature_spec.name == "test_feature"
        assert feature_spec.dim == 10

        # Verify only name and dim fields exist
        field_names = {f.name for f in fields(BaseFeatureSpec)}
        assert field_names == {"name", "dim"}

        # Verify dtype and description do not exist
        assert not hasattr(feature_spec, "dtype")
        assert not hasattr(feature_spec, "description")

    def test_feature_spec_model_has_only_name_and_dim(self):
        """Test that model FeatureSpec has only name and dim fields."""
        feature_spec = ModelFeatureSpec(name="model_feature", dim=20)

        # Verify instance was created successfully
        assert feature_spec.name == "model_feature"
        assert feature_spec.dim == 20

        # Verify only name and dim fields exist
        field_names = {f.name for f in fields(ModelFeatureSpec)}
        assert field_names == {"name", "dim"}

        # Verify description does not exist
        assert not hasattr(feature_spec, "description")
