"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Inference Logger Module

Centralized logging for neural inference:
1. Features (observation vector components)
2. Output results (actions and control commands)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rclpy.impl.rcutils_logger import RcutilsLogger


class InferenceLogger:
  """Centralized logger for neural inference data.

  Logs:
  - Features (observation vector components) - to file
  - Output results (raw actions, processed control commands)
  """

  def __init__(
    self,
    logger: RcutilsLogger,
    log_interval: int = 100,
    enable_output: bool = True,
    enable_features: bool = False,
    features_log_file: str | None = None,
  ):
    """Initialize the inference logger.

    Args:
        logger: ROS2 logger instance
        log_interval: Log every N steps (default 100)
        enable_output: Whether to log output results
        enable_features: Whether to log features to file
        features_log_file: Path to features log file (default: /tmp/neural_features.log)

    """
    self._logger = logger
    self._log_interval = log_interval
    self._enable_output = enable_output
    self._enable_features = enable_features
    self._features_log_file = features_log_file or "/tmp/neural_features.log"
    self._step_count = 0

    if self._enable_features:
      Path(self._features_log_file).write_text("")

  def log_output(
    self,
    raw_action: np.ndarray,
    thrust_acc_norm: float,
    flu_ang_vel: np.ndarray,
    frd_ang_vel: np.ndarray,
    enu_to_target: np.ndarray | None = None,
  ) -> None:
    """Log output results after inference.

    Args:
        raw_action: Raw action from neural network [thrust, roll_rate, pitch_rate, yaw_rate]
        thrust_acc_norm: Normalized thrust acceleration [-1, 1]
        flu_ang_vel: Processed angular rates in FLU frame [roll, pitch, yaw] rad/s
        frd_ang_vel: Processed angular rates in FRD frame [roll, pitch, yaw] rad/s
        enu_to_target: Target error vector in ENU frame [e, n, -d] (meters)

    """
    self._step_count += 1

    if not self._enable_output:
      return

    if self._step_count % self._log_interval != 0:
      return

    self._logger.info("-" * 40)
    self._logger.info(f"[OUTPUT] Step {self._step_count}")
    self._logger.info(
      f"  raw_actions: [{raw_action[0]:+.4f}, {raw_action[1]:+.4f}, "
      f"{raw_action[2]:+.4f}, {raw_action[3]:+.4f}]"
    )
    self._logger.info("  processed_actions:")
    self._logger.info(f"    thrust_acc_norm: {thrust_acc_norm:+.4f}  (thrust-axis acc command)")
    self._logger.info("  ------- policy frame (FLU) -------")
    self._logger.info(
      f"    flu_ang_vel: [{flu_ang_vel[0]:+.4f}, {flu_ang_vel[1]:+.4f}, "
      f"{flu_ang_vel[2]:+.4f}] rad/s"
    )
    self._logger.info("  ------- control publisher frame (FRD) -------")
    self._logger.info(
      f"    frd_ang_vel: [{frd_ang_vel[0]:+.4f}, {frd_ang_vel[1]:+.4f}, "
      f"{frd_ang_vel[2]:+.4f}] rad/s"
    )
    if enu_to_target is not None:
      self._logger.info(
        f"    enu_to_target: [{enu_to_target[0]:+.4f}, {enu_to_target[1]:+.4f}, "
        f"{enu_to_target[2]:+.4f}]"
      )
    self._logger.info("-" * 4)

  def log_features(
    self,
    obs: np.ndarray,
    feature_specs: list,
  ) -> None:
    """Log feature vector components to file only.

    Args:
        obs: Full observation vector
        feature_specs: List of FeatureSpec with name and dim

    """
    if not self._enable_features:
      return

    if self._step_count % self._log_interval != 0:
      return

    lines = []
    offset = 0
    for spec in feature_specs:
      feat_vec = obs[offset : offset + spec.dim]
      feat_str = ", ".join(f"{v:+.4f}" for v in feat_vec)
      line = f"  {spec.name}: [{feat_str}] (dim={spec.dim})"
      lines.append(line)
      offset += spec.dim

    with open(self._features_log_file, "a") as f:
      f.write(
        "\n".join(["=" * 60, f"[FEATURES] Step {self._step_count}", "-" * 50] + lines + ["=" * 60])
        + "\n"
      )

  def set_log_interval(self, interval: int) -> None:
    """Set logging interval."""
    self._log_interval = max(1, interval)

  def enable_output_logging(self, enable: bool) -> None:
    """Enable/disable output logging."""
    self._enable_output = enable

  def enable_features_logging(self, enable: bool) -> None:
    """Enable/disable features logging."""
    self._enable_features = enable

  def reset(self) -> None:
    """Reset step counter."""
    self._step_count = 0
