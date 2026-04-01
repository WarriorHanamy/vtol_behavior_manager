"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Neural Position Control Node for PX4

This node implements neural network inference for position control:
1. Subscribe to VehicleOdometry topic
2. Compose observation using VtolFeatureProvider
3. Run ONNX inference using MLPPolicyActor
4. Publish VehicleAccRatesSetpoint control commands
"""

from __future__ import annotations

from pathlib import Path

import hydra
import numpy as np
import rclpy.node
from omegaconf.omegaconf import DictConfig

from neural_manager.neural_inference.control.action_post_processor import ActionPostProcessor
from neural_manager.neural_inference.features import RevisionContext, VtolFeatureProvider
from neural_manager.neural_inference.inference.actors import MLPPolicyActor
from neural_manager.neural_inference.logging import InferenceLogger
from px4_msgs.msg import VehicleAccRatesSetpoint

ARTIFACTS_ROOT = Path("/home/ros")
DEFAULT_TASK = "vtol_hover"


class NeuralControlNode(rclpy.node.Node):
  """Neural position control node with discovery-based model loading."""

  def __init__(self, cfg: DictConfig):
    self.cfg = cfg

    self._revision_ctx = self._resolve_revision_context()

    super().__init__(self.cfg.node.name)

    self._feature_provider = VtolFeatureProvider(
      self._revision_ctx.metadata_path,
      node=self,
      odometry_topic=self.cfg.node.odometry_topic,
      target_topic=self.cfg.node.target_topic,
    )

    self._policy_actor = self._create_policy_actor()

    self._action_processor = ActionPostProcessor(
      min_thrust_g=self.cfg.control.min_thrust_g,
      max_thrust_g=self.cfg.control.max_thrust_g,
      max_ang_vel=tuple(self.cfg.control.max_ang_vel),
      node_logger=self.get_logger(),
      acc_fixed=self.cfg.debug.acc_fixed,
      use_tanh_activation=self.cfg.control.action_processing.use_tanh_activation,
      enable_action_clipping=self.cfg.control.action_processing.enable_action_clipping,
      action_limits={
        "min": -1.0,
        "max": 1.0,
      },
      print_control_commands=self.cfg.debug.print_control,
      ros_node=self,
    )

    self._control_pub = self.create_publisher(
      VehicleAccRatesSetpoint,
      self.cfg.node.setpoint_topic,
      10,
    )

    log_interval = getattr(self.cfg.debug, "log_interval", 100)
    enable_features = getattr(self.cfg.debug, "enable_features", False)
    features_log_file = getattr(self.cfg.debug, "features_log_file", "/tmp/neural_features.log")

    self._inference_logger = InferenceLogger(
      logger=self.get_logger(),
      log_interval=log_interval,
      enable_output=True,
      enable_features=enable_features,
      features_log_file=features_log_file,
    )
    self._feature_specs = self._feature_provider.get_feature_specs()

    self._last_action = np.zeros(4, dtype=np.float32)
    self._step_count = 0

    self.get_logger().info("🚀 Neural control node initialized")
    self.get_logger().info(f"  Revision: {self._revision_ctx.revision_path.name}")
    self.get_logger().info(f"  Obs dim: {self._revision_ctx.obs_dim}")

  def _resolve_revision_context(self) -> RevisionContext:
    """Resolve model revision via discovery. Raises on failure."""
    task = getattr(self.cfg.model, "task", DEFAULT_TASK)
    ctx = RevisionContext.from_discovery(ARTIFACTS_ROOT, task)
    print(f"✓ Discovered revision: {ctx.revision_path.name}")
    print(f"  Model: {ctx.model_path}")
    print(f"  Obs dim: {ctx.obs_dim}")
    return ctx

  def _create_policy_actor(self) -> MLPPolicyActor:
    """Create policy actor from discovered revision."""
    expected_input_shape = list(self._revision_ctx.get_expected_input_shape())
    expected_output_shape = list(self._revision_ctx.get_expected_output_shape())

    self.get_logger().info(
      f"Model shapes - input: {expected_input_shape}, output: {expected_output_shape}"
    )

    actor = MLPPolicyActor(
      self._revision_ctx.model_path,
      providers=self.cfg.model.inference.providers,
      node_logger=self.get_logger(),
      expected_input_shape=expected_input_shape,
      expected_output_shape=expected_output_shape,
    )

    self.get_logger().info("✓ MLP policy actor created")
    return actor

  def run_inference(self) -> None:
    """Run neural inference and publish control command."""
    self._feature_provider.update_last_action(self._last_action)

    obs = self._feature_provider.get_all_features()
    self._inference_logger.log_features(obs, self._feature_specs)

    raw_action = self._policy_actor(obs)

    control_msg = self._action_processor.process_action(raw_action)

    output = self._action_processor.get_last_output()
    self._inference_logger.log_output(
      raw_action=raw_action,
      thrust_acc=output["thrust_acc"],
      frd_ang_vel=output["frd_ang_vel"],
    )

    self._control_pub.publish(control_msg)

    self._last_action = raw_action.copy()

    self._step_count += 1
    if self.cfg.debug.print_observation and self._step_count % 100 == 0:
      self.get_logger().info(f"Step {self._step_count}: obs={obs[:5]}... action={raw_action}")


@hydra.main(version_base="1.2", config_path="config", config_name="pos_ctrl_config")
def main(cfg: DictConfig) -> int:
  """Main entry point."""
  rclpy.init()

  try:
    node = NeuralControlNode(cfg)
    rclpy.spin(node)
  except FileNotFoundError as e:
    print(f"❌ Discovery failed: {e}")
    rclpy.shutdown()
    return 1
  except KeyboardInterrupt:
    print("用户中断，正在关闭...")
  except Exception as e:
    print(f"❌ Node error: {e}")
    rclpy.shutdown()
    return 1
  finally:
    if "node" in locals():
      node.destroy_node()
    rclpy.shutdown()

  return 0


if __name__ == "__main__":
  main()
