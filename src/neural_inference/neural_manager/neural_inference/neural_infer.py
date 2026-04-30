"""Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Neural Position Control Node for PX4

Lifecycle-aware node that runs neural network inference for position control:
1. on_configure: create ROS interfaces (publisher, subscribers, timer)
2. on_activate: enable lifecycle publisher
3. _on_target: build pipeline on first /neural/target, rebuild on task switch
4. _run_inference: timer callback — skip if pipeline not ready
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from rclpy.lifecycle import Node, State, TransitionCallbackReturn
from rclpy.qos import qos_profile_sensor_data

from goal_msgs.msg import NeuralTarget
from neural_manager.neural_inference.control.action_post_processor import ActionPostProcessor
from neural_manager.neural_inference.features import (
  RevisionContext,
  VtolAcroFeatureProvider,
  VtolHoverFeatureProvider,
)
from neural_manager.neural_inference.inference.actors import BasePolicyActor, MLPPolicyActor
from neural_manager.neural_inference.inference.tensorrt_utils.tensorrt_actor import (
  TensorRTMLPActor,
)
from neural_manager.neural_inference.logging import InferenceLogger
from px4_msgs.msg import VehicleAccRatesSetpoint, VehicleOdometry

ARTIFACTS_ROOT = Path("/home/ros")

TASK_FEATURE_PROVIDERS: dict[str, type] = {
  "vtol_hover": VtolHoverFeatureProvider,
  "vtol_acro": VtolAcroFeatureProvider,
}


def _load_action_metadata(revision_path: Path) -> dict | None:
  """Load action_metadata.yaml from revision directory if present."""
  action_path = revision_path / "action_metadata.yaml"
  if not action_path.exists():
    return None
  with open(action_path) as f:
    return yaml.safe_load(f)


class NeuralControlNode(Node):
  """Neural position control lifecycle node.

  Lifecycle:
    unconfigured -> (on_configure) -> inactive -> (on_activate) -> active
    active -> (on_deactivate) -> inactive
    inactive -> (on_cleanup) -> unconfigured

  Pipeline deferred until first /neural/target message.
  Task switching rebuilds pipeline in-place (no deactivate/cleanup).
  """

  def __init__(self, node_name: str = "neural_infer_node", **kwargs):
    self._feature_provider = None
    self._policy_actor = None
    self._action_processor = None
    self._current_task: int | None = None
    self._last_action = np.zeros(4, dtype=np.float32)
    self._step_count = 0
    self._inference_logger: InferenceLogger | None = None
    self._feature_specs = []
    super().__init__(node_name, **kwargs)

  # ---- Lifecycle callbacks ----

  def on_configure(self, state: State) -> TransitionCallbackReturn:
    """Create all ROS interfaces. Model loading deferred until first target."""
    # Parameters
    self.declare_parameter("setpoint_topic", "/fmu/in/vehicle_acc_rates_setpoint")
    self.declare_parameter("odometry_topic", "/fmu/out/vehicle_odometry")
    self.declare_parameter("target_topic", "/neural/target")
    self.declare_parameter("inference_backend", "onnx")
    self.declare_parameter("inference_providers", ["CPUExecutionProvider"])
    self.declare_parameter("engine_path", "")
    self.declare_parameter("inference_hz", 50.0)
    self.declare_parameter("odom_rate", 100.0)
    self.declare_parameter("use_tanh_activation", False)
    self.declare_parameter("enable_action_clipping", True)
    self.declare_parameter("acc_fixed", False)
    self.declare_parameter("print_observation", False)
    self.declare_parameter("print_control", False)
    self.declare_parameter("log_interval", 10)
    self.declare_parameter("enable_features", False)
    self.declare_parameter("features_log_file", "/tmp/neural_features.log")

    setpoint_topic = self.get_parameter("setpoint_topic").value
    odometry_topic = self.get_parameter("odometry_topic").value
    target_topic = self.get_parameter("target_topic").value

    # Lifecycle publisher — inactive -> publish() is silent no-op
    self._control_pub = self.create_lifecycle_publisher(
      VehicleAccRatesSetpoint, setpoint_topic, 10
    )

    # Subscriptions work in all lifecycle states
    self._target_sub = self.create_subscription(NeuralTarget, target_topic, self._on_target, 10)

    self._odom_sub = self.create_subscription(
      VehicleOdometry, odometry_topic, self._on_odom, qos_profile_sensor_data
    )

    # Inference timer — fires at configured rate
    inference_hz = float(self.get_parameter("inference_hz").value)
    self._timer = self.create_timer(1.0 / inference_hz, self._run_inference)

    self._inference_logger = InferenceLogger(
      logger=self.get_logger(),
      log_interval=self.get_parameter("log_interval").value,
      enable_output=True,
      enable_features=self.get_parameter("enable_features").value,
      features_log_file=self.get_parameter("features_log_file").value,
    )

    self.get_logger().info("Configured — waiting for /neural/target")
    return TransitionCallbackReturn.SUCCESS

  def on_activate(self, state: State) -> TransitionCallbackReturn:
    self.get_logger().info("Activated")
    return super().on_activate(state)

  def on_deactivate(self, state: State) -> TransitionCallbackReturn:
    self.get_logger().info("Deactivated")
    return super().on_deactivate(state)

  def on_cleanup(self, state: State) -> TransitionCallbackReturn:
    self.destroy_timer(self._timer)
    self.destroy_publisher(self._control_pub)
    self._feature_provider = None
    self._policy_actor = None
    self._action_processor = None
    self._current_task = None
    self.get_logger().info("Cleaned up")
    return TransitionCallbackReturn.SUCCESS

  def on_shutdown(self, state: State) -> TransitionCallbackReturn:
    self.destroy_timer(self._timer)
    self.destroy_publisher(self._control_pub)
    return TransitionCallbackReturn.SUCCESS

  # ---- Business logic ----

  def _on_target(self, msg: NeuralTarget) -> None:
    """Build pipeline on first target; rebuild inline on task switch."""
    task_type = msg.task_type

    if task_type == self._current_task:
      self._route_target(msg)
      return

    self.get_logger().info(f"Task: {self._current_task} -> {task_type}")
    self._build_pipeline(task_type)
    self._route_target(msg)

  def _route_target(self, msg: NeuralTarget) -> None:
    """Route sub-message to feature provider."""
    if self._feature_provider is None:
      return
    if msg.task_type == NeuralTarget.TASK_HOVER:
      self._feature_provider.update_from_goal_hover(msg.goal_hover)
    elif msg.task_type == NeuralTarget.TASK_ACRO:
      self._feature_provider.update_from_goal_acro(msg.goal_acro)

  def _build_pipeline(self, task_type: int) -> None:
    """Discover model, create feature provider + policy actor + action post-processor."""
    task_name = "vtol_hover" if task_type == NeuralTarget.TASK_HOVER else "vtol_acro"

    ctx = RevisionContext.from_discovery(ARTIFACTS_ROOT, task_name)
    self.get_logger().info(f"Revision: {ctx.revision_path.name}")
    self.get_logger().info(f"  Model: {ctx.model_path}")
    self.get_logger().info(f"  Obs dim: {ctx.obs_dim}")

    provider_cls = TASK_FEATURE_PROVIDERS.get(task_name)
    if provider_cls is None:
      raise ValueError(f"No feature provider for task '{task_name}'")

    odom_rate = float(self.get_parameter("odom_rate").value)
    inference_hz = float(self.get_parameter("inference_hz").value)

    # Feature provider without ROS subscriptions — node manages odom/target
    self._feature_provider = provider_cls(
      ctx.metadata_path,
      node=None,
      odometry_topic=None,
      target_topic=None,
      odom_rate=odom_rate,
      inference_rate=inference_hz,
    )

    self._policy_actor = self._create_policy_actor(ctx)

    action_meta = _load_action_metadata(ctx.revision_path)
    if action_meta is not None:
      min_thrust_g = float(action_meta["min_thrust"])
      max_thrust_g = float(action_meta["max_thrust"])
      max_ang_vel = tuple(action_meta["max_ang_vel"])
      self.get_logger().info(f"Loaded action_metadata: {action_meta}")
    else:
      self.get_logger().warn("action_metadata.yaml not found. Using hardcoded defaults.")
      min_thrust_g = 0.0
      max_thrust_g = 2.0
      max_ang_vel = (3.0, 3.0, 1.0)

    self._action_processor = ActionPostProcessor(
      min_thrust_g=min_thrust_g,
      max_thrust_g=max_thrust_g,
      max_ang_vel=max_ang_vel,
      node_logger=self.get_logger(),
      acc_fixed=self.get_parameter("acc_fixed").value,
      use_tanh_activation=self.get_parameter("use_tanh_activation").value,
      enable_action_clipping=self.get_parameter("enable_action_clipping").value,
      action_limits={"min": -1.0, "max": 1.0},
      print_control_commands=self.get_parameter("print_control").value,
      ros_node=self,
    )

    self._feature_specs = self._feature_provider.get_feature_specs()
    self._current_task = task_type
    self.get_logger().info(f"Pipeline built for: {task_name}")

  def _create_policy_actor(self, ctx: RevisionContext) -> BasePolicyActor:
    """Create policy actor from discovered revision."""
    input_shape = list(ctx.get_expected_input_shape())
    output_shape = list(ctx.get_expected_output_shape())
    self.get_logger().info(f"Shapes — input: {input_shape}, output: {output_shape}")

    backend = self.get_parameter("inference_backend").value

    if backend == "tensorrt":
      engine_path = self._resolve_engine_path(ctx)
      return TensorRTMLPActor(
        engine_path,
        node_logger=self.get_logger(),
        expected_input_shape=input_shape,
        expected_output_shape=output_shape,
      )

    providers = self.get_parameter("inference_providers").value
    return MLPPolicyActor(
      ctx.model_path,
      providers=providers,
      node_logger=self.get_logger(),
      expected_input_shape=input_shape,
      expected_output_shape=output_shape,
    )

  def _resolve_engine_path(self, ctx: RevisionContext) -> Path:
    """Resolve TensorRT engine path from param or revision context."""
    cfg_engine = self.get_parameter("engine_path").value
    if cfg_engine:
      return Path(cfg_engine)
    if ctx.engine_path is not None:
      return ctx.engine_path
    raise FileNotFoundError("No TensorRT engine found")

  def _on_odom(self, msg: VehicleOdometry) -> None:
    """Buffer odometry in feature provider. Inference driven by timer."""
    if self._feature_provider is None:
      return
    ned_position = np.array([msg.position[0], msg.position[1], msg.position[2]], dtype=np.float32)
    ned_velocity = np.array([msg.velocity[0], msg.velocity[1], msg.velocity[2]], dtype=np.float32)
    ned_quat_frd = np.array([msg.q[0], msg.q[1], msg.q[2], msg.q[3]], dtype=np.float32)
    frd_ang_vel = np.array(
      [msg.angular_velocity[0], msg.angular_velocity[1], msg.angular_velocity[2]], dtype=np.float32
    )
    self._feature_provider.update_vehicle_odom(
      ned_position, ned_velocity, ned_quat_frd, frd_ang_vel
    )

  def _run_inference(self) -> None:
    """Timer callback. Silent no-op if pipeline not ready or node inactive."""
    if self._feature_provider is None:
      return

    self._feature_provider.update_last_action(self._last_action)
    obs = self._feature_provider.get_all_features()
    self._inference_logger.log_features(obs, self._feature_specs)

    raw_action = self._policy_actor(obs)
    control_msg = self._action_processor.process_action(raw_action)

    output = self._action_processor.get_last_output()
    enu_to_target = getattr(self._feature_provider, "get_enu_to_target", lambda: np.zeros(3))()
    self._inference_logger.log_output(
      raw_action=raw_action,
      thrust_acc_norm=output["thrust_acc_norm"],
      flu_ang_vel=output["flu_ang_vel"],
      frd_ang_vel=output["frd_ang_vel"],
      enu_to_target=enu_to_target,
    )

    self._control_pub.publish(control_msg)
    self._last_action = raw_action.copy()

    self._step_count += 1
    if self.get_parameter("print_observation").value and self._step_count % 100 == 0:
      self.get_logger().info(f"Step {self._step_count}: obs={obs[:5]}... action={raw_action}")


def main():
  """Main entry point — standard ROS2 convention (no Hydra)."""
  import rclpy

  rclpy.init()
  node = NeuralControlNode()
  try:
    node.trigger_configure()
    rclpy.spin(node)
  except KeyboardInterrupt:
    pass
  finally:
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
  main()
