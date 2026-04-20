"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Revision Context Module

Holds discovered revision paths and metadata for neural network inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .feature_provider_base import FeatureSpec
from .revision_discoverer import RevisionDiscoverer


@dataclass
class RevisionContext:
  """Holds discovered revision paths and metadata.

  This class encapsulates all information needed to run inference
  with a discovered model revision, including paths and dimensions.
  """

  revision_path: Path
  model_path: Path
  engine_path: Path | None = None
  metadata_path: Path
  feature_specs: list[FeatureSpec]
  obs_dim: int
  action_dim: int = 4

  @classmethod
  def from_discovery(cls, artifacts_root: Path | str, task: str) -> RevisionContext:
    """Create RevisionContext by discovering the latest revision.

    Args:
        artifacts_root: Base directory containing policies/ subdirectory
        task: Task name (e.g., "vtol_hover")

    Returns:
        RevisionContext with discovered paths and dimensions

    Raises:
        FileNotFoundError: If no valid revision is found

    """
    artifacts_root = Path(artifacts_root)

    latest = RevisionDiscoverer.discover_latest(artifacts_root, task)
    if latest is None:
      raise FileNotFoundError(
        f"No valid revision found for task '{task}' in {artifacts_root}. "
        f"Expected: {artifacts_root}/policies/{task}/<revision>/ "
        f"containing model.onnx and observations_metadata.yaml"
      )

    metadata_path = latest / "observations_metadata.yaml"

    with open(metadata_path) as f:
      meta = yaml.safe_load(f)

    specs = [FeatureSpec(name=f["name"], dim=f["dim"]) for f in meta.get("low_dim", [])]
    obs_dim = sum(s.dim for s in specs)

    engine_path = latest / "vtol_hover.fp16.engine"
    if not engine_path.exists():
      engine_path = None

    return cls(
      revision_path=latest,
      model_path=latest / "model.onnx",
      engine_path=engine_path,
      metadata_path=metadata_path,
      feature_specs=specs,
      obs_dim=obs_dim,
      action_dim=4,
    )

  def get_expected_input_shape(self) -> tuple[int, int]:
    """Get expected model input shape [batch, obs_dim]."""
    return (1, self.obs_dim)

  def get_expected_output_shape(self) -> tuple[int, int]:
    """Get expected model output shape [batch, action_dim]."""
    return (1, self.action_dim)

  def __str__(self) -> str:
    return (
      f"RevisionContext(\n"
      f"  revision={self.revision_path.name},\n"
      f"  engine={self.engine_path},\n"
      f"  model={self.model_path},\n"
      f"  obs_dim={self.obs_dim},\n"
      f"  action_dim={self.action_dim},\n"
      f"  features={[f'{s.name}:{s.dim}' for s in self.feature_specs]}\n"
      f")"
    )
