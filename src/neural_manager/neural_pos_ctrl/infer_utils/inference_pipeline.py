#!/usr/bin/env python3
"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Neural Inference Pipeline Orchestrator

Coordinates all components to provide the complete neural control pipeline.
Manages the flow from odometry input to control output with proper error handling.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
import rclpy.node
from px4_msgs.msg import VehicleOdometry

from .actors import BasePolicyActor
from .action_post_processor import ActionPostProcessor
from .communicator import Communicator
from .history_buffer import ObservationHistoryBuffer
from .observation_processor import ObservationProcessor


class NeuralInferencePipeline:
    """
    Main orchestrator for the neural inference pipeline.
    Coordinates all components to provide end-to-end neural control functionality.
    """

    def __init__(
        self,
        node: rclpy.node.Node,
        policy_actor,
        observation_processor: ObservationProcessor,
        action_post_processor: ActionPostProcessor,
        communicator: Communicator,
        history_buffer: Optional[ObservationHistoryBuffer] = None,
    ):
        """
        Initialize the neural inference pipeline.

        Args:
            node: ROS2 node instance
            policy_actor: Neural network policy actor (GRU or MLP)
            observation_processor: Component for processing odometry to observations
            action_post_processor: Component for processing neural output to control commands
            communicator: Component for ROS2 communication
            history_buffer: Optional history buffer for MLP actors
        """
        self._node = node
        self._policy_actor = policy_actor
        self._observation_processor = observation_processor
        self._action_post_processor = action_post_processor
        self._communicator = communicator
        self._history_buffer = history_buffer

        # Pipeline state
        self._active = True
        self._model_loaded = True
        self._init_success = False
        self._last_action = np.zeros(4, dtype=np.float32)

        # Timing and statistics
        self._last_odom_sample_time = 0.0
        self._inference_count = 0
        self._total_inference_time = 0.0
        self._start_time = time.time()
        self._debug_timer = self.create_debug_timer()

    def initialize(self) -> bool:
        """
        Initialize all pipeline components.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize communicator components
            if not self._communicator.initialize_publishers():
                self._node.get_logger().error("发布者初始化失败")
                return False

            if not self._communicator.initialize_subscribers(self._odometry_callback):
                self._node.get_logger().error("订阅者初始化失败")
                return False

            # Reset actor and buffer state
            self._policy_actor.reset()
            if self._history_buffer is not None:
                self._history_buffer.reset()

            self._init_success = True
            self._node.get_logger().info("🚀 神经推理管道初始化成功!")
            return True

        except Exception as e:
            self._node.get_logger().error(f"管道初始化失败: {e}")
            return False

    def _odometry_callback(self, msg: VehicleOdometry):
        """
        Main callback for processing VehicleOdometry messages.

        Args:
            msg: VehicleOdometry ROS2 message
        """
        if not self._is_ready_for_processing():
            return

        # Update timing
        self._last_odom_sample_time = msg.timestamp_sample

        # Process odometry to observation
        observation, is_first_frame = self._observation_processor.process_vehicle_odometry(msg)
        if observation is None:
            self._node.get_logger().warning("观测数据处理失败")
            return

        # Append last action to observation (20 dims total: 16 obs + 4 last action)
        observation_with_action = np.concatenate([observation, self._last_action])

        # Handle observation history for MLP actors
        if self._history_buffer is not None:
            self._history_buffer.add_observation(observation_with_action)
            inference_observation = self._history_buffer.get_stacked_history()
        else:
            # Use single observation for GRU actors
            inference_observation = observation_with_action

        # Print observation (excluding the first frame to avoid noise)
        if not is_first_frame:
            self._observation_processor.print_observation(observation_with_action)

        # Execute neural network inference
        start_time = time.perf_counter()
        raw_action = self.run_inference(inference_observation)
        inference_time = (time.perf_counter() - start_time) * 1000.0  # Convert to milliseconds

        if raw_action is None:
            self._node.get_logger().error("推理失败")
            return

        # Update statistics
        self._inference_count += 1
        self._total_inference_time += inference_time

        # Validate and process action
        if not self._action_post_processor.validate_action(raw_action):
            self._node.get_logger().warning(f"动作验证失败: {raw_action}")
            return

        # Convert action for display and print
        action_display = self._action_post_processor.convert_action_for_display(raw_action)
        self._action_post_processor.print_control_command(action_display)

        # Process action to PX4 control message
        control_msg = self._action_post_processor.process_action(raw_action)

        # Publish control command
        if self._communicator.publish_control_setpoint_with_validation(control_msg):
            self._last_action = raw_action.copy()
        else:
            self._node.get_logger().warning("控制指令发布失败")

    def run_inference(self, observation: np.ndarray) -> Optional[np.ndarray]:
        """
        Run neural network inference.

        Args:
            observation: Input observation for the neural network

        Returns:
            Raw action from neural network or None if inference failed
        """
        if not self._model_loaded or not self._active:
            self._node.get_logger().warning(
                "模型未加载或神经网络控制未激活，跳过推理"
            )
            return None

        try:
            action = self._policy_actor(observation)
            # Ensure output is clipped to [-1, 1] range
            action = np.clip(action, -1.0, 1.0)
            return action
        except Exception as e:
            self._node.get_logger().error(f"推理错误: {e}")
            return None

    def create_debug_timer(self, callback_period: float = 5.0):
        """
        Create debug timer callback for status monitoring.

        Args:
            callback_period: Period in seconds for debug callbacks
        """
        if not self._init_success:
            return

        debug_timer = self._node.create_timer(callback_period, self._debug_callback)
        self._node.get_logger().info(f"调试定时器已创建，周期: {callback_period:.1f}s")
        return debug_timer

    def _debug_callback(self):
        """Debug callback for periodic status reporting."""
        if not self._init_success:
            return

        # Calculate data age
        current_time = time.time() * 1e6  # Convert to microseconds
        data_age = (current_time - self._last_odom_sample_time) / 1000.0  # Convert to milliseconds

        # Get component statistics for debug logging
        pipeline_info = self.get_pipeline_info()
        comm_stats = self._communicator.get_communication_stats()
        actor_stats = self._policy_actor.get_inference_stats()

        # Log debug status
        status = "激活" if self._active else "停用"
        self._node.get_logger().info(
            f"系统状态: 神经网络控制={status}, 数据延迟={data_age:.1f}ms, "
            f"目标位置=({self._observation_processor._target_position[0]:.3f}, "
            f"{self._observation_processor._target_position[1]:.3f}, "
            f"{self._observation_processor._target_position[2]:.3f}), "
            f"推理次数={actor_stats['inference_count']}, "
            f"平均推理时间={actor_stats['average_inference_time']:.2f}ms"
        )

    def _is_ready_for_processing(self) -> bool:
        """
        Check if pipeline is ready for processing new data.

        Returns:
            True if ready, False otherwise
        """
        if not self._init_success:
            return False

        if not self._model_loaded:
            self._node.get_logger().warning("模型未加载")
            return False

        if not self._active:
            self._node.get_logger().warning("神经网络控制未激活")
            return False

        return True

    def get_pipeline_info(self) -> dict:
        """
        Get comprehensive pipeline information for debugging.

        Returns:
            Dictionary containing pipeline state and statistics
        """
        current_time = time.time()
        uptime = current_time - self._start_time

        info = {
            "active": self._active,
            "model_loaded": self._model_loaded,
            "init_success": self._init_success,
            "uptime_seconds": uptime,
            "inference_count": self._inference_count,
            "average_inference_time": self._total_inference_time / max(self._inference_count, 1),
            "inference_rate": self._inference_count / uptime if uptime > 0 else 0.0,
            "last_action": self._last_action.tolist(),
            "actor_type": type(self._policy_actor).__name__,
            "history_buffer_enabled": self._history_buffer is not None,
        }

        # Add component-specific information
        if self._history_buffer is not None:
            info["history_buffer"] = self._history_buffer.get_info()

        return info

    def get_all_components_info(self) -> dict:
        """
        Get information from all pipeline components.

        Returns:
            Dictionary containing information from all components
        """
        return {
            "pipeline": self.get_pipeline_info(),
            "observation_processor": self._observation_processor.get_observation_info(),
            "action_post_processor": self._action_post_processor.get_processor_info(),
            "communicator": self._communicator.get_topic_info(),
            "communicator_stats": self._communicator.get_communication_stats(),
            "policy_actor": self._policy_actor.get_inference_stats(),
        }

    def set_active(self, active: bool):
        """
        Set pipeline active/inactive state.

        Args:
            active: Whether the pipeline should be active
        """
        self._active = active
        status = "激活" if active else "停用"
        self._node.get_logger().info(f"神经网络控制已{status}")

    def reset(self):
        """Reset pipeline state for fresh start."""
        # Reset actor and buffer
        self._policy_actor.reset()
        if self._history_buffer is not None:
            self._history_buffer.reset()

        # Reset observation processor
        self._observation_processor.reset()

        # Reset action post processor
        self._action_post_processor.reset()

        # Reset statistics
        self._last_action = np.zeros(4, dtype=np.float32)
        self._inference_count = 0
        self._total_inference_time = 0.0
        self._start_time = time.time()
        self._last_odom_sample_time = 0.0

        # Reset communicator statistics
        self._communicator.reset_statistics()

        self._node.get_logger().info("🔄 神经推理管道已重置")

    def shutdown(self):
        """Clean shutdown of all pipeline components."""
        self._active = False
        self._model_loaded = False

        # Shutdown communicator
        self._communicator.shutdown()

        self._node.get_logger().info("🔄 神经推理管道已关闭")