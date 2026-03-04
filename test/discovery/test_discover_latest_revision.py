"""
Test for RevisionDiscoverer discover_latest() method.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import tempfile
from datetime import datetime

import pytest

from features.revision_discoverer import RevisionDiscoverer


class TestDiscoverLatestRevision:
    """Test that discover_latest() returns the latest valid revision."""

    def test_multiple_valid_revisions_returns_latest(self):
        """Test that discover_latest() returns the revision with latest timestamp."""
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
                (rev / "observations_metadata.yaml").touch()

            # Call discover_latest
            result = RevisionDiscoverer.discover_latest(artifacts_root, task)

            # Should return the latest revision (rev3)
            assert result == rev3

    def test_no_valid_revisions_returns_none(self):
        """Test that discover_latest() returns None when no valid revisions exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            task = "test_task"

            # Create task directory with invalid revision (missing files)
            task_dir = artifacts_root / "policies" / task
            task_dir.mkdir(parents=True)

            rev = task_dir / "test_task-20260303T110451Z-hash1"
            rev.mkdir()
            # Do not create required files

            # Call discover_latest
            result = RevisionDiscoverer.discover_latest(artifacts_root, task)

            # Should return None
            assert result is None

    def test_empty_task_directory_returns_none(self):
        """Test that discover_latest() returns None when task directory is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            task = "test_task"

            # Create empty task directory
            task_dir = artifacts_root / "policies" / task
            task_dir.mkdir(parents=True)

            # Call discover_latest
            result = RevisionDiscoverer.discover_latest(artifacts_root, task)

            # Should return None
            assert result is None

    def test_missing_task_directory_returns_none(self):
        """Test that discover_latest() returns None when task directory does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            task = "test_task"

            # Do not create task directory

            # Call discover_latest
            result = RevisionDiscoverer.discover_latest(artifacts_root, task)

            # Should return None
            assert result is None

    def test_single_valid_revision_returns_it(self):
        """Test that discover_latest() returns the single valid revision."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            task = "test_task"

            # Create task directory
            task_dir = artifacts_root / "policies" / task
            task_dir.mkdir(parents=True)

            # Create single revision
            rev = task_dir / "test_task-20260303T110451Z-hash1"
            rev.mkdir()
            (rev / "model.onnx").touch()
            (rev / "observations_metadata.yaml").touch()

            # Call discover_latest
            result = RevisionDiscoverer.discover_latest(artifacts_root, task)

            # Should return the revision
            assert result == rev

    def test_mixed_valid_invalid_returns_latest_valid(self):
        """Test that discover_latest() filters invalid revisions and returns latest valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            task = "test_task"

            # Create task directory
            task_dir = artifacts_root / "policies" / task
            task_dir.mkdir(parents=True)

            # Create mix of valid and invalid revisions
            rev1 = task_dir / "test_task-20260301T100000Z-hash1"
            rev2 = task_dir / "test_task-20260302T120000Z-hash2"  # Invalid
            rev3 = task_dir / "test_task-20260303T110451Z-hash3"

            # rev1: valid
            rev1.mkdir()
            (rev1 / "model.onnx").touch()
            (rev1 / "observations_metadata.yaml").touch()

            # rev2: invalid (missing model.onnx)
            rev2.mkdir()
            (rev2 / "observations_metadata.yaml").touch()

            # rev3: valid (latest)
            rev3.mkdir()
            (rev3 / "model.onnx").touch()
            (rev3 / "observations_metadata.yaml").touch()

            # Call discover_latest
            result = RevisionDiscoverer.discover_latest(artifacts_root, task)

            # Should return rev3 (latest valid)
            assert result == rev3
