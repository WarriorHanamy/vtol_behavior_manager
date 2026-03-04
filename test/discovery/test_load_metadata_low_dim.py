"""
Test for _load_metadata() parsing low_dim format (FR-3).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import tempfile

import pytest

from features.feature_provider_base import FeatureProviderBase


class MockFeatureProvider(FeatureProviderBase):
    """Mock feature provider for testing."""

    def __init__(self, metadata_path):
        super().__init__(metadata_path)

    def get_feature1(self):
        return [1.0, 2.0, 3.0]

    def get_feature2(self):
        return [4.0, 5.0]


class TestLoadMetadataLowDim:
    """Test that _load_metadata() correctly parses low_dim format."""

    def test_load_metadata_parses_valid_low_dim_format(self):
        """Test that _load_metadata() correctly parses valid low_dim format."""
        # Create a temporary metadata file with low_dim format
        metadata_content = {
            "low_dim": [
                {"name": "feature1", "dim": 3},
                {"name": "feature2", "dim": 2},
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            yaml.dump(metadata_content, f)
            temp_path = f.name

        try:
            # Create feature provider
            provider = MockFeatureProvider(temp_path)

            # Verify metadata was loaded correctly
            assert len(provider._metadata) == 2
            assert provider._metadata[0].name == "feature1"
            assert provider._metadata[0].dim == 3
            assert provider._metadata[1].name == "feature2"
            assert provider._metadata[1].dim == 2
        finally:
            Path(temp_path).unlink()

    def test_load_metadata_handles_empty_low_dim_list(self):
        """Test that _load_metadata() handles empty low_dim list gracefully."""
        # Create a temporary metadata file with empty low_dim list
        metadata_content = {"low_dim": []}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            yaml.dump(metadata_content, f)
            temp_path = f.name

        try:
            # Create feature provider
            provider = MockFeatureProvider(temp_path)

            # Verify metadata is empty list
            assert len(provider._metadata) == 0
        finally:
            Path(temp_path).unlink()
