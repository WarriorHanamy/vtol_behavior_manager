"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Revision Discoverer Module

This module provides functionality to discover the latest model revision
by timestamp from a policies directory structure.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class RevisionDiscoverer:
  """Discoverer for finding the latest model revision by timestamp.

  This class scans policies/<task>/ directories and returns the latest
  revision based on timestamp extracted from directory names.

  Revision directory format: {task_name}-{timestamp}-{hash}
  Example: vtol_hover-20260303T110451Z-bd60e47b-746b0cb9
  """

  @staticmethod
  def discover_latest(artifacts_root: Path | str, task: str) -> Path | None:
    """Discover the latest revision for a given task.

    Scans <artifacts_root>/policies/<task>/ directory, filters valid
    revisions (both model.onnx and observations_metadata.yaml present),
    sorts by timestamp descending, and returns the path to the latest
    revision directory.

    Args:
        artifacts_root: Base directory containing policies/ subdirectory
        task: Task name (e.g., "vtol_hover")

    Returns:
        Path to the latest revision directory, or None if no valid
        revisions are found

    Examples:
        >>> latest = RevisionDiscoverer.discover_latest("/path/to/artifacts", "vtol_hover")
        >>> print(latest)
        /path/to/artifacts/policies/vtol_hover/vtol_hover-20260303T110451Z-abc123

    """
    artifacts_root = Path(artifacts_root)
    task_dir = artifacts_root / "policies" / task

    # Check if task directory exists
    if not task_dir.exists():
      return None

    # Collect and filter valid revisions
    valid_revisions: list[tuple[datetime, Path]] = []
    for rev_dir in task_dir.iterdir():
      if not rev_dir.is_dir():
        continue

      if not RevisionDiscoverer._validate_revision(rev_dir):
        continue

      timestamp = RevisionDiscoverer._parse_revision_name(rev_dir.name)
      if timestamp is None:
        continue

      valid_revisions.append((timestamp, rev_dir))

    # If no valid revisions, return None
    if not valid_revisions:
      return None

    # Sort by timestamp descending and return latest
    valid_revisions.sort(key=lambda x: x[0], reverse=True)

    return valid_revisions[0][1]

  @staticmethod
  def _parse_revision_name(revision_dir_name: str) -> datetime | None:
    """Extract timestamp from revision directory name.

    Revision directory name format: {task_name}-{timestamp}-{hash}
    Timestamp format: YYYYMMDDTHHMMSSZ (ISO 8601 compact format)

    Args:
        revision_dir_name: Revision directory name

    Returns:
        Datetime object representing the timestamp, or None if parsing fails

    Examples:
        >>> RevisionDiscoverer._parse_revision_name("vtol_hover-20260303T110451Z-abc123")
        datetime.datetime(2026, 3, 3, 11, 4, 51, tzinfo=datetime.timezone.utc)

    """
    try:
      # Split by dash and extract timestamp part
      parts = revision_dir_name.split("-")

      # Need at least 2 parts: name and timestamp
      if len(parts) < 2:
        return None

      timestamp_str = parts[1]

      # Parse ISO 8601 compact format: YYYYMMDDTHHMMSSZ
      # Convert to standard format for parsing
      # YYYYMMDDTHHMMSSZ -> YYYY-MM-DDTHH:MM:SSZ
      if len(timestamp_str) != 16 or timestamp_str[8] != "T" or timestamp_str[-1] != "Z":
        return None

      year = int(timestamp_str[0:4])
      month = int(timestamp_str[4:6])
      day = int(timestamp_str[6:8])
      hour = int(timestamp_str[9:11])
      minute = int(timestamp_str[11:13])
      second = int(timestamp_str[13:15])

      return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except (ValueError, IndexError):
      return None

  @staticmethod
  def _validate_revision(revision_path: Path) -> bool:
    """Validate that a revision directory contains required files.

    Checks that both model.onnx and observations_metadata.yaml exist
    in the revision directory.

    Args:
        revision_path: Path to revision directory

    Returns:
        True if both required files exist, False otherwise

    Examples:
        >>> RevisionDiscoverer._validate_revision(Path("/path/to/revision"))
        True

    """
    model_path = revision_path / "model.onnx"
    metadata_path = revision_path / "observations_metadata.yaml"

    return model_path.exists() and metadata_path.exists()
