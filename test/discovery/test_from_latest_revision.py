"""
Test for FeatureProviderBase.from_latest_revision() class method.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import tempfile
from datetime import datetime

import pytest
import yaml

from neural_manager.neural_inference.features.feature_provider_base import FeatureProviderBase
from neural_manager.neural_inference.features.revision_discoverer import RevisionDiscoverer


class MockFeatureProvider(FeatureProviderBase):
  """Mock subclass of FeatureProviderBase for testing."""

  def __init__(self, metadata_path: Path | str):
    self.features_called = []
    super().__init__(metadata_path)

  def get_test_feature(self):
    """Mock feature method."""
    self.features_called.append("test_feature")
    return [1.0, 2.0, 3.0]


class TestFromLatestRevision:
  """Test that from_latest_revision() discovers and initializes from latest revision."""

  def test_valid_revisions_returns_initialized_provider(self):
    """
    Test that from_latest_revision() returns a properly initialized provider
    instance when valid revisions exist.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
      artifacts_root = Path(tmpdir)
      task = "test_task"

      # Create task directory
      task_dir = artifacts_root / "policies" / task
      task_dir.mkdir(parents=True)

      # Create three revisions with different timestamps
      rev1 = task_dir / "test_task-20260301T100000Z-hash1"
      rev2 = task_dir / "test_task-20260302T120000Z-hash2"
      rev3 = task_dir / "test_task-20260303T110451Z-hash3"

      for rev in [rev1, rev2, rev3]:
        rev.mkdir()
        (rev / "model.onnx").touch()

      # Create valid metadata for each revision
      metadata_content = {
        "low_dim": [
          {"name": "test_feature", "dim": 3},
        ]
      }

      for rev in [rev1, rev2, rev3]:
        metadata_path = rev / "observations_metadata.yaml"
        with open(metadata_path, "w") as f:
          yaml.dump(metadata_content, f)

      # Call from_latest_revision
      provider = MockFeatureProvider.from_latest_revision(artifacts_root, task)

      # Verify provider is correctly initialized
      assert isinstance(provider, MockFeatureProvider)
      assert provider._metadata_path == rev3 / "observations_metadata.yaml"
      assert len(provider._metadata) == 1
      assert provider._metadata[0].name == "test_feature"
      assert provider._metadata[0].dim == 3
      assert all(result.passed for result in provider._validation_results)

  def test_no_valid_revisions_raises_file_not_found(self):
    """
    Test that from_latest_revision() raises FileNotFoundError with clear message
    when no valid revisions exist.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
      artifacts_root = Path(tmpdir)
      task = "test_task"

      # Create empty task directory (no revisions)
      task_dir = artifacts_root / "policies" / task
      task_dir.mkdir(parents=True)

      # Call from_latest_revision and expect FileNotFoundError
      with pytest.raises(FileNotFoundError) as exc_info:
        MockFeatureProvider.from_latest_revision(artifacts_root, task)

      # Verify error message is clear and informative
      error_message = str(exc_info.value)
      assert "No valid revision found" in error_message
      assert str(artifacts_root) in error_message
      assert task in error_message

  def test_multiple_revisions_selects_latest_timestamp(self):
    """
    Test that from_latest_revision() selects the revision with the latest
    timestamp when multiple valid revisions exist.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
      artifacts_root = Path(tmpdir)
      task = "test_task"

      # Create task directory
      task_dir = artifacts_root / "policies" / task
      task_dir.mkdir(parents=True)

      # Create five revisions with different timestamps
      timestamps = [
        "20260301T100000Z",
        "20260302T120000Z",
        "20260303T110451Z",
        "20260304T090000Z",  # Latest
        "20260305T080000Z",  # Even more latest
      ]

      metadata_content = {
        "low_dim": [
          {"name": "test_feature", "dim": 3},
        ]
      }

      revisions = []
      for i, timestamp in enumerate(timestamps):
        rev = task_dir / f"test_task-{timestamp}-hash{i}"
        rev.mkdir()
        (rev / "model.onnx").touch()
        metadata_path = rev / "observations_metadata.yaml"
        with open(metadata_path, "w") as f:
          yaml.dump(metadata_content, f)
        revisions.append(rev)

      # Call from_latest_revision
      provider = MockFeatureProvider.from_latest_revision(artifacts_root, task)

      # Should initialize from the last revision (latest timestamp)
      assert provider._metadata_path == revisions[-1] / "observations_metadata.yaml"

  def test_missing_task_directory_raises_file_not_found(self):
    """
    Test that from_latest_revision() raises FileNotFoundError when task
    directory does not exist.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
      artifacts_root = Path(tmpdir)
      task = "non_existent_task"

      # Do not create task directory

      # Call from_latest_revision and expect FileNotFoundError
      with pytest.raises(FileNotFoundError) as exc_info:
        MockFeatureProvider.from_latest_revision(artifacts_root, task)

      # Verify error message mentions the issue
      error_message = str(exc_info.value)
      assert "No valid revision found" in error_message

  def test_string_artifacts_root_path_works(self):
    """
    Test that from_latest_revision() works with string path for artifacts_root.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
      artifacts_root = tmpdir  # String, not Path
      task = "test_task"

      # Create task directory
      task_dir = Path(tmpdir) / "policies" / task
      task_dir.mkdir(parents=True)

      # Create single revision
      rev = task_dir / "test_task-20260303T110451Z-hash1"
      rev.mkdir()
      (rev / "model.onnx").touch()

      metadata_content = {
        "low_dim": [
          {"name": "test_feature", "dim": 3},
        ]
      }

      metadata_path = rev / "observations_metadata.yaml"
      with open(metadata_path, "w") as f:
        yaml.dump(metadata_content, f)

      # Call from_latest_revision with string path
      provider = MockFeatureProvider.from_latest_revision(artifacts_root, task)

      # Verify provider is correctly initialized
      assert isinstance(provider, MockFeatureProvider)
      assert provider._metadata_path == rev / "observations_metadata.yaml"
