"""Tests for action_metadata loading."""

from pathlib import Path

import yaml


def _load_action_metadata(revision_path: Path) -> dict | None:
  """Load action_metadata.yaml from revision directory if present.

  Duplicate of neural_infer._load_action_metadata — kept separate
  so tests don't require rclpy import.
  """
  action_path = revision_path / "action_metadata.yaml"
  if not action_path.exists():
    return None
  with open(action_path) as f:
    return yaml.safe_load(f)


class TestLoadActionMetadata:
  def test_loads_valid_yaml(self, tmp_action_metadata):
    revision_dir = tmp_action_metadata(
      max_ang_vel=[5.0, 4.0, 2.0],
      min_thrust=0.5,
      max_thrust=2.5,
    )
    result = _load_action_metadata(revision_dir)
    assert result is not None
    assert result["max_ang_vel"] == [5.0, 4.0, 2.0]
    assert result["min_thrust"] == 0.5
    assert result["max_thrust"] == 2.5

  def test_returns_none_when_missing(self, tmp_path):
    result = _load_action_metadata(tmp_path)
    assert result is None

  def test_loads_default_values(self, tmp_action_metadata):
    revision_dir = tmp_action_metadata()
    result = _load_action_metadata(revision_dir)
    assert result is not None
    assert result["min_thrust"] == 0.0
    assert result["max_thrust"] == 2.0

  def test_handles_empty_yaml(self, tmp_path):
    path = tmp_path / "action_metadata.yaml"
    path.write_text("")
    result = _load_action_metadata(tmp_path)
    # yaml.safe_load("") returns None
    assert result is None
