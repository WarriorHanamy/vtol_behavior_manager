"""Test for RevisionDiscoverer _validate_revision() method.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import tempfile

from neural_manager.neural_inference.features.revision_discoverer import RevisionDiscoverer


class TestValidateRevision:
  """Test that _validate_revision() validates revision directory contents."""

  def test_valid_revision_returns_true(self):
    """Test that _validate_revision() returns True when both files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
      rev_path = Path(tmpdir) / "test_revision"
      rev_path.mkdir()

      # Create both required files
      (rev_path / "model.onnx").touch()
      (rev_path / "observations_metadata.yaml").touch()

      result = RevisionDiscoverer._validate_revision(rev_path)

      # Should return True
      assert result is True

  def test_missing_model_returns_false(self):
    """Test that _validate_revision() returns False when model.onnx is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
      rev_path = Path(tmpdir) / "test_revision"
      rev_path.mkdir()

      # Create only observations_metadata.yaml
      (rev_path / "observations_metadata.yaml").touch()

      result = RevisionDiscoverer._validate_revision(rev_path)

      # Should return False
      assert result is False

  def test_missing_metadata_returns_false(self):
    """Test that _validate_revision() returns False when observations_metadata.yaml is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
      rev_path = Path(tmpdir) / "test_revision"
      rev_path.mkdir()

      # Create only model.onnx
      (rev_path / "model.onnx").touch()

      result = RevisionDiscoverer._validate_revision(rev_path)

      # Should return False
      assert result is False

  def test_both_missing_returns_false(self):
    """Test that _validate_revision() returns False when both files are missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
      rev_path = Path(tmpdir) / "test_revision"
      rev_path.mkdir()

      # Do not create any files

      result = RevisionDiscoverer._validate_revision(rev_path)

      # Should return False
      assert result is False

  def test_extra_files_present_returns_true(self):
    """Test that _validate_revision() returns True when both required files exist with extra files."""
    with tempfile.TemporaryDirectory() as tmpdir:
      rev_path = Path(tmpdir) / "test_revision"
      rev_path.mkdir()

      # Create both required files
      (rev_path / "model.onnx").touch()
      (rev_path / "observations_metadata.yaml").touch()

      # Create extra files
      (rev_path / "extra_file.txt").touch()
      (rev_path / "data.csv").touch()

      result = RevisionDiscoverer._validate_revision(rev_path)

      # Should return True (extra files don't matter)
      assert result is True

  def test_nonexistent_directory_raises_error(self):
    """Test that _validate_revision() handles non-existent directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
      rev_path = Path(tmpdir) / "nonexistent_revision"

      # Should not raise error, just return False
      result = RevisionDiscoverer._validate_revision(rev_path)

      # Should return False
      assert result is False
