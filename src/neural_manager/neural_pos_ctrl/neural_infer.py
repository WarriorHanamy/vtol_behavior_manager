#!/usr/bin/env python3
"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Isaac Position Control Neural Network Inference Node for PX4 (Refactored)

该节点实现从Isaac训练的位置控制模型的ROS2推理功能：
1. 订阅VehicleOdometry和mode_neural_ctrl话题
2. 将PX4 NED坐标系数据转换为Isaac训练格式的观测
3. 使用ONNX Runtime进行神经网络推理
4. 发布VehicleRatesSetpoint控制指令

这个重构版本使用模块化组件架构，提供更好的可测试性和可维护性。
"""

from __future__ import annotations

from typing import Optional

import hydra
import numpy as np
import rclpy
import rclpy.node
from omegaconf.omegaconf import DictConfig, OmegaConf

# Import refactored components
from infer_utils.actors import GRUPolicyActor, MLPPolicyActor
from infer_utils.inference_pipeline import NeuralInferencePipeline
from infer_utils.observation_processor import ObservationProcessor
from infer_utils.action_post_processor import ActionPostProcessor
from infer_utils.communicator import Communicator
from infer_utils.history_buffer import ObservationHistoryBuffer

class NeuralControlNode(rclpy.node.Node):
    """Neural位置控制神经网络推理节点 (重构版本)"""

    def __init__(self, cfg: DictConfig):
        """初始化推理节点"""
        super().__init__(self.cfg.node.name)
        # Store configuration
        self.cfg = cfg

        # Pipeline instance
        self._pipeline: Optional[NeuralInferencePipeline] = None

        if self.init_components():
            self.get_logger().info("🚀 Neural控制节点初始化成功!")
        else:
            self.get_logger().error("❌ 组件初始化失败，节点无法启动")

    def init_components(self) -> bool:
        """Initialize all components and create inference pipeline."""
        try:
            # Load configuration parameters
            target_position = np.array(self.cfg.target.position, dtype=np.float32)
            target_yaw = self.cfg.target.yaw

            # Create policy actor based on configuration
            policy_actor = self._create_policy_actor()

            if policy_actor is None:
                return False

            # Create observation processor
            observation_processor = ObservationProcessor(
                target_position=target_position,
                target_yaw=target_yaw,
                node_logger=self.get_logger(),
                enable_input_saturation=self.cfg.control.input_saturation.enabled,
                saturation_limits={
                    "target_position": self.cfg.control.input_saturation.target_position
                },
                print_observations=self.cfg.debug.print_observation
            )

            # Create action post processor
            action_post_processor = ActionPostProcessor(
                thrust_acc_base=self.cfg.control.thrust_acc,
                max_roll_pitch_rate=self.cfg.control.max_roll_pitch_rate,
                max_yaw_rate=self.cfg.control.max_yaw_rate,
                node_logger=self.get_logger(),
                acc_fixed=self.cfg.debug.acc_fixed,
                enable_action_clipping=self.cfg.model.inference.output_clipping.enabled,
                action_limits={
                    "min": self.cfg.model.inference.output_clipping.min,
                    "max": self.cfg.model.inference.output_clipping.max
                },
                print_control_commands=self.cfg.debug.print_control
            )

            # Create communicator
            communicator = Communicator(
                node=self,
                odometry_topic=self.cfg.node.odometry_topic,
                setpoint_topic=self.cfg.node.setpoint_topic
            )

            # Create history buffer if needed (for MLP actors)
            history_buffer = None
            if self.cfg.model.actor_type == "mlp" and self.cfg.model.history.enabled:
                history_buffer = ObservationHistoryBuffer(
                    history_length=self.cfg.model.history.length,
                    obs_dim=self.cfg.model.history.obs_dim,
                    node_logger=self.get_logger()
                )

            # Create and initialize pipeline
            self._pipeline = NeuralInferencePipeline(
                node=self,
                policy_actor=policy_actor,
                observation_processor=observation_processor,
                action_post_processor=action_post_processor,
                communicator=communicator,
                history_buffer=history_buffer
            )

            if not self._pipeline.initialize():
                self.get_logger().error("❌ 管道初始化失败")
                return False
            return True

        except Exception as e:
            self.get_logger().error(f"❌ 组件初始化失败: {e}")
            return False

    def _create_policy_actor(self) -> Optional[object]:
        """Create policy actor based on configuration."""
        try:
            # Get actor type and providers
            actor_type = self.cfg.model.actor_type
            providers = self.cfg.model.inference.providers
            model_path = self.cfg.model.path

            # Get expected shapes for validation (always required)
            expected_shapes = self.cfg.model.expected_shapes[actor_type]
            expected_input_shape = expected_shapes.input
            expected_output_shape = expected_shapes.output

            # Create actor based on type
            if actor_type == "gru":
                self.get_logger().info("使用 GRU 执行器")
                actor = GRUPolicyActor(
                    model_path,
                    hidden_dim=self.cfg.model.hidden_dim,
                    num_layers=self.cfg.model.num_layers,
                    providers=providers,
                    node_logger=self.get_logger(),
                    expected_input_shape=expected_input_shape,
                    expected_output_shape=expected_output_shape,
                )
            elif actor_type == "mlp":
                self.get_logger().info("使用 MLP 执行器")
                actor = MLPPolicyActor(
                    model_path,
                    providers=providers,
                    node_logger=self.get_logger(),
                    expected_input_shape=expected_input_shape,
                    expected_output_shape=expected_output_shape,
                )
            else:
                self.get_logger().error(f"不支持的执行器类型: {actor_type}")
                return None

            return actor

        except Exception as e:
            self.get_logger().error(f"❌ 创建策略执行器失败: {e}")
            return None

    def get_pipeline_info(self) -> dict:
        """Get comprehensive pipeline information."""
        if self._pipeline is None:
            return {"status": "not_initialized"}

        return self._pipeline.get_all_components_info()


    def shutdown_pipeline(self):
        """Shutdown the inference pipeline."""
        if self._pipeline is not None:
            self._pipeline.shutdown()
            self._pipeline = None


@hydra.main(version_base="1.2", config_path="conf", config_name="pos_ctrl_config")
def main(cfg: DictConfig) -> int:
    """主函数"""
    rclpy.init()

    try:
        node = NeuralControlNode(cfg)
        if node._pipeline.initialize():
            rclpy.spin(node)
        else:
            rclpy.shutdown()
            return 1

    except KeyboardInterrupt:
        print("用户中断，正在关闭...")
    except Exception as e:
        print(f"节点运行错误: {e}")
        return 1
    finally:
        # Ensure pipeline is properly shutdown
        if 'node' in locals() and hasattr(node, 'shutdown_pipeline'):
            node.shutdown_pipeline()
        rclpy.shutdown()

    return 0


if __name__ == "__main__":
    main()