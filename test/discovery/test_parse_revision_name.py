"""Test for RevisionDiscoverer _parse_revision_name() method.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from datetime import datetime, timezone

from neural_manager.neural_inference.features.revision_discoverer import RevisionDiscoverer


class TestParseRevisionName:
  """Test that _parse_revision_name() extracts timestamp correctly."""

  def test_standard_format_extracts_timestamp(self):
    """Test that _parse_revision_name() extracts timestamp from standard format."""
    revision_name = "vtol_hover-20260303T110451Z-bd60e47b-746b0cb9"

    result = RevisionDiscoverer._parse_revision_name(revision_name)

    # Should return datetime object with correct timestamp
    assert result == datetime(2026, 3, 3, 11, 4, 51, tzinfo=timezone.utc)

  def test_invalid_format_returns_none(self):
    """Test that _parse_revision_name() returns None for invalid format."""
    revision_name = "invalid_name_without_timestamp"

    result = RevisionDiscoverer._parse_revision_name(revision_name)

    # Should return None
    assert result is None

  def test_malformed_timestamp_returns_none(self):
    """Test that _parse_revision_name() returns None for malformed timestamp."""
    revision_name = "vtol_hover-invalid-timestamp-hash"

    result = RevisionDiscoverer._parse_revision_name(revision_name)

    # Should return None
    assert result is None

  def test_missing_hash_part_extracts_timestamp(self):
    """Test that _parse_revision_name() works even if hash is missing."""
    revision_name = "vtol_hover-20260303T110451Z"

    result = RevisionDiscoverer._parse_revision_name(revision_name)

    # Should still extract timestamp
    assert result == datetime(2026, 3, 3, 11, 4, 51, tzinfo=timezone.utc)
