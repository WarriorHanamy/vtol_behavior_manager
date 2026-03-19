"""
Test for RevisionDiscoverer export from features module.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

import neural_manager.neural_inference.features as features
from neural_manager.neural_inference.features import RevisionDiscoverer


class TestExportRevisionDiscoverer:
  """Test that RevisionDiscoverer is exported from features module."""

  def test_can_import_revision_discoverer_from_features(self):
    """Test that RevisionDiscoverer can be imported from features."""
    # This import should work

    # Should be a class
    assert isinstance(RevisionDiscoverer, type)

    # Should have required methods
    assert hasattr(RevisionDiscoverer, "discover_latest")
    assert hasattr(RevisionDiscoverer, "_parse_revision_name")
    assert hasattr(RevisionDiscoverer, "_validate_revision")

  def test_revision_discoverer_in_all_exports(self):
    """Test that RevisionDiscoverer is in __all__ exports."""
    # Check __all__ contains RevisionDiscoverer
    assert "RevisionDiscoverer" in features.__all__

  def test_revision_discoverer_accessible_via_attributes(self):
    """Test that RevisionDiscoverer is accessible via module attributes."""
    # Should be accessible via attributes
    assert hasattr(features, "RevisionDiscoverer")
    assert features.RevisionDiscoverer is not None

  def test_revision_discoverer_matches_imported_class(self):
    """Test that RevisionDiscoverer in __all__ matches the imported class."""

    # Should match
    assert features.__all__.count("RevisionDiscoverer") == 1
    assert features.RevisionDiscoverer is RevisionDiscoverer
