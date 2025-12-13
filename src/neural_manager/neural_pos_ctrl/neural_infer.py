#!/usr/bin/env python3
"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

Isaac Position Control Neural Network Inference Node for PX4

该节点实现从Isaac训练的位置控制模型的ROS2推理功能：
1. 订阅VehicleOdometry和mode_neural_ctrl话题
2. 将PX4 NED坐标系数据转换为Isaac训练格式的20维观测
3. 使用ONNX Runtime进行神经网络推理
4. 发布VehicleRatesSetpoint控制指令
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from tkinter.constants import CURRENT
from typing import Optional

import hydra
import numpy as np
import onnxruntime as ort
import rclpy
import rclpy.node
import rclpy.qos
from omegaconf.omegaconf import DictConfig, OmegaConf
from px4_msgs.msg import VehicleOdometry, VehicleThrustAccSetpoint
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Bool

from gru_executor import GRUPolicyExecutor
from math_utils import (
    frd_flu_rotate,
    quat_act_rot,
    quat_pas_rot,
    quat_right_multiply_flu_frd,
    quaternion_to_euler,
    rotation_matrix_body_to_ned,
    rotation_matrix_ned_to_body,
)
from mlp_executor import MLPPolicyExecutor


class NeuralControlNode(rclpy.node.Node):
    """Neural位置控制神经网络推理节点"""

    def __init__(self, cfg: DictConfig):
        """初始化推理节点"""
        super().__init__(cfg.node.name)
        # Store configuration
        self.cfg = cfg

        # 监控信息
        self._model_loaded = False
        self._inference_session: ort.InferenceSession | None = None
        self._active = True
        self._last_odom_sample_time = 0.0
        self._last_odom_receive_time = 0.0
        self._first_odom_received = False  # 标记是否收到第一帧
        self._init_success = False

        # 接收间隔统计
        self._receive_interval_samples = []
        self._sample_interval_samples = []
        self._last_interval_report_time = 0.0
        self._interval_report_period = 5.0

        # 加载配置参数
        self._model_path = Path(cfg.model.path)
        self._control_rate = cfg.control.update_rate
        self._control_period = cfg.control.update_period
        self._target_position = np.array(
            cfg.target.position, dtype=np.float32
        )  # NED坐标系
        self._target_yaw = cfg.target.yaw
        self._max_roll_pitch_rate = cfg.control.max_roll_pitch_rate
        self._max_yaw_rate = cfg.control.max_yaw_rate

        self._last_action = np.zeros(4, dtype=np.float32)
        # 初始化ONNX模型
        if self.init_model():
            # 创建发布者和订阅者
            self.init_publishers()
            self.init_subscribers()
            self.init_timers()
            self._init_success = True
            self.get_logger().info("🚀 Neural控制节点初始化成功!")
        else:
            self.get_logger().error("❌ 模型初始化失败，节点无法启动")

    def init_model(self) -> bool:
        if not self._model_path.exists():
            self.get_logger().error(f"模型文件不存在: {self._model_path}")
            return False
        self.get_logger().info(f"加载ONNX模型: {self._model_path}")

        # Create executor based on configuration
        executor_type = self.cfg.model.executor_type
        providers = self.cfg.model.inference.providers

        if executor_type == "gru":
            self.get_logger().info("使用 GRU 执行器")
            self._policy_executor = GRUPolicyExecutor(
                self._model_path,
                hidden_dim=self.cfg.model.hidden_dim,
                num_layers=self.cfg.model.num_layers,
                providers=providers,
            )
        elif executor_type == "mlp":
            self.get_logger().info("使用 MLP 执行器")
            self._policy_executor = MLPPolicyExecutor(
                self._model_path, providers=providers
            )
        else:
            self.get_logger().error(f"不支持的执行器类型: {executor_type}")
            return False

        # Get model input/output information
        input_info = self._policy_executor.session.get_inputs()[0]
        output_info = self._policy_executor.session.get_outputs()[0]

        self._input_name = input_info.name
        self._output_name = output_info.name
        self._input_shape = input_info.shape
        self._output_shape = output_info.shape

        self.get_logger().info("模型信息:")
        self.get_logger().info(f"  执行器类型: {executor_type}")
        self.get_logger().info(f"  输入: {self._input_name}, 形状: {self._input_shape}")
        self.get_logger().info(
            f"  输出: {self._output_name}, 形状: {self._output_shape}"
        )

        # Validate shapes based on executor type
        expected_shapes = self.cfg.model.expected_shapes[executor_type]
        expected_input_shape = expected_shapes.input
        expected_output_shape = expected_shapes.output

        if self.cfg.model.inference.validate_shapes:
            if self._input_shape != expected_input_shape:
                self.get_logger().error(
                    f"输入形状不匹配，期望 {expected_input_shape}，实际 {self._input_shape}"
                )
                return False

            if self._output_shape != expected_output_shape:
                self.get_logger().error(
                    f"输出形状不匹配，期望 {expected_output_shape}，实际 {self._output_shape}"
                )
                return False

        self._model_loaded = True
        self.get_logger().info("✅ ONNX模型加载成功!")

        # Reset executor state (important for GRU)
        self._policy_executor.reset()

        return True

    def init_publishers(self):
        """初始化发布者"""
        # 控制指令发布者
        self._acc_rates_publisher = self.create_publisher(
            VehicleThrustAccSetpoint,
            self.cfg.node.setpoint_topic,
            qos_profile=qos_profile_sensor_data,
        )
        self.get_logger().info("发布者已初始化")

    def init_subscribers(self):
        """初始化订阅者"""
        # VehicleOdometry
        self._odometry_subscriber = self.create_subscription(
            VehicleOdometry,
            self.cfg.node.odometry_topic,
            self.odometry_callback,
            rclpy.qos.qos_profile_sensor_data,
        )

        self.get_logger().info("订阅者已初始化")

    def init_timers(self):
        """初始化定时器"""
        # 控制发布定时器
        self._control_timer = self.create_timer(
            self._control_period, self.control_timer_callback
        )

        self._debug_timer = self.create_timer(5.0, self.debug_callback)

        self.get_logger().info(f"定时器已初始化，控制周期: {self._control_period:.3f}s")

    def odometry_callback(self, msg: VehicleOdometry):
        """VehicleOdometry回调函数"""

        # 检查数据新鲜度
        current_receive_time = time.time() * 1e6  # 转换为微秒
        current_sample_time = msg.timestamp_sample

        # 跳过第一帧的检查
        if not self._first_odom_received:
            self._first_odom_received = True
            self._last_odom_receive_time = current_receive_time
            self._last_odom_sample_time = current_sample_time
            self._last_interval_report_time = time.time()
            self.get_logger().info("✅ 收到第一帧里程计数据")
            return

        # 计算接收间隔
        receive_interval = (
            current_receive_time - self._last_odom_receive_time
        ) / 1000.0  # ms
        sample_interval = (
            current_sample_time - self._last_odom_sample_time
        ) / 1000.0  # ms

        # 检查接收间隔超时
        timeout_ms = self.cfg.control.timeout_ms
        if receive_interval > timeout_ms:
            self.get_logger().error(
                f"⚠️ 里程计接收间隔: {receive_interval:.1f} ms，数据过时"
            )
        else:
            # 记录正常的接收间隔用于统计
            self._receive_interval_samples.append(receive_interval)
            # 限制样本数量
            if len(self._receive_interval_samples) > 100:
                self._receive_interval_samples.pop(0)

        # 检查采样间隔超时
        if sample_interval > timeout_ms:
            self.get_logger().error(
                f"⚠️ 里程计采样间隔: {sample_interval:.1f} ms，数据过时"
            )
        else:
            # 记录正常的采样间隔用于统计
            self._sample_interval_samples.append(sample_interval)
            # 限制样本数量
            if len(self._sample_interval_samples) > 100:
                self._sample_interval_samples.pop(0)

        # 定期报告平均间隔
        current_time = time.time()
        if current_time - self._last_interval_report_time >= 5.0:
            if self._receive_interval_samples and self._sample_interval_samples:
                avg_receive = np.mean(self._receive_interval_samples)
                avg_sample = np.mean(self._sample_interval_samples)
                self.get_logger().info(
                    f"📊 里程计统计 (最近{len(self._receive_interval_samples)}帧): "
                    f"平均接收间隔={avg_receive:.1f}ms, 平均采样间隔={avg_sample:.1f}ms"
                )
            self._last_interval_report_time = current_time

        # 更新时间戳
        self._last_odom_receive_time = current_receive_time
        self._last_odom_sample_time = current_sample_time

        if not self._model_loaded or not self._active:
            self.get_logger().warn(
                "模型未加载或神经网络控制未激活，跳过里程计数据处理", once=True
            )
            return

        # 检查数据有效性
        if msg.timestamp_sample == 0 or np.allclose(msg.position, [0.0, 0.0, 0.0]):
            self.get_logger().warn("无效的里程计数据")
            return

        observation = self.process_odometry_to_observation(msg)
        self.print_observation(observation)
        if observation is None:
            self.get_logger().warn("观测数据处理失败")
            return

        # 执行神经网络推理（包含耗时计算）
        start_time = time.perf_counter()
        action = self.run_inference(observation)
        inference_time = (time.perf_counter() - start_time) * 1000.0  # 转换为毫秒

        if action is not None:
            # 打印控制指令
            self.print_control_command(action)
            # 立即发布控制指令

            self.publish_control_command(action)
            # 输出推理耗时（如果启用性能监控）
            if self.cfg.debug.measure_inference_time:
                self.get_logger().info(f"🧠 神经网络推理耗时: {inference_time:.2f} ms")

    def control_timer_callback(self):
        if not self._model_loaded or not self._active:
            self.get_logger().warn(
                "模型未加载或神经网络控制未激活，跳过控制定时器回调", once=True
            )
            return

    def debug_callback(self):
        """调试信息回调函数"""
        if not self._init_success:
            return
        status = "激活" if self._active else "停用"
        data_age = (time.time() * 1e6 - self._last_odom_sample_time) / 1000.0
        self.get_logger().info("🔍 调试状态:")
        self.get_logger().info(f"  神经网络控制: {status}")
        self.get_logger().info(f"  数据延迟: {data_age:.1f} ms")
        self.get_logger().info(f"  目标位置(NED): {self._target_position}")

    def process_odometry_to_observation(
        self, msg: VehicleOdometry
    ) -> Optional[np.ndarray]:
        """
        将VehicleOdometry转换为16维观测向量

        基于drone_pos_ctrl_env_cfg.py的Policy输入结构：
        1. lin_vel (3维): [vx, vy, vz]
        2. projected_gravity_b (3维): [gx, gy, gz]
        3. ang_vel (3维): [wx, wy, wz]
        4. current_yaw_direction (2维): [cos(yaw), sin(yaw)]
        5. target_pos_b (3维): 目标位置(机体坐标系)
        6. target_yaw (2维): 目标偏航方向

        Args:
            msg: VehicleOdometry消息

        Returns:
            16维观测向量或None(数据无效时)
        """
        pos = np.array(msg.position, dtype=np.float32)  # NED坐标系 [x, y, z]
        vel = np.array(msg.velocity, dtype=np.float32)  # 参考frame [vx, vy, vz]
        ang_vel_b_frd = np.array(
            msg.angular_velocity, dtype=np.float32
        )  # 机体frame [wx, wy, wz]
        quat_frd = np.array(msg.q, dtype=np.float32)  # [w, x, y, z] Hamilton约定
        quat_flu = quat_right_multiply_flu_frd(quat_frd)

        gra_dir_w = np.array([0.0, 0.0, 1.0])  # NED坐标系的向上重力
        lin_vel_b_flu = quat_pas_rot(quat_flu, vel)
        ang_vel_b_flu = frd_flu_rotate(ang_vel_b_frd)
        gra_dir_b_flu = quat_pas_rot(quat_flu, gra_dir_w)

        # lin_vel_b_flu = np.zeros_like(lin_vel_b_flu)
        target_pos_w = self._target_position
        to_target = target_pos_w - pos

        to_target_pos_b_flu = quat_pas_rot(quat_flu, to_target)
        to_target_pos_b_flu[2] = 0.0  # 忽略垂直方向误差

        target_yaw_dir = np.array(
            [math.cos(self._target_yaw), math.sin(self._target_yaw)]
        )
        current_yaw_dir = np.array([math.cos(0.0), math.sin(0.0)])
        target_yaw_dir = current_yaw_dir

        observation = np.concatenate(
            [
                lin_vel_b_flu,  # 3维: 机体线速度 [vx, vy, vz]
                ang_vel_b_flu,  # 3维: 机体角速度 [wx, wy, wz]
                to_target_pos_b_flu,  # 3维: 目标位置(机体) [dx, dy, dz]
                gra_dir_b_flu,  # 3维: 机体重力投影 [gx, gy, gz]
                current_yaw_dir,  # 2维: 当前偏航方向 [cos(yaw), sin(yaw)]
                target_yaw_dir,  # 2维: 目标偏航方向 [cos(target_yaw), sin(target_yaw)]
                self._last_action,  # 4维: 上一帧动作
            ],
            dtype=np.float32,
        )

        # # 应用输入饱和限制
        observation = self.apply_obs_saturation(observation)

        return observation

    def print_observation(self, observation: np.ndarray):
        """
        Print observation vector by semantic order

        Args:
            observation: 16维观测向量
        """
        if observation is None:
            return
        if not self.cfg.debug.print_observation:
            return
        # 解构观测向量
        lin_vel_b = observation[0:3]  # 机体线速度
        ang_vel_b = observation[3:6]  # 机体角速度
        to_target_pos_b = observation[6:9]  # 目标位置(机体)
        gra_dir_b = observation[9:12]  # 机体重力投影
        current_yaw_dir = observation[12:14]  # 当前偏航方向
        target_yaw_dir = observation[14:16]  # 目标偏航方向

        print(
            f"  🎯 目标位置(机体): [{to_target_pos_b[0]:.3f}, {to_target_pos_b[1]:.3f}, {to_target_pos_b[2]:.3f}]"
        )
        print(
            f"  🚁 机体线速度:     [{lin_vel_b[0]:.3f}, {lin_vel_b[1]:.3f}, {lin_vel_b[2]:.3f}]"
        )
        print(
            f"  🔄 机体角速度:     [{ang_vel_b[0]:.3f}, {ang_vel_b[1]:.3f}, {ang_vel_b[2]:.3f}]"
        )
        print(
            f"  🌍 重力投影:       [{gra_dir_b[0]:.3f}, {gra_dir_b[1]:.3f}, {gra_dir_b[2]:.3f}]"
        )
        print(
            f"  🧭 当前偏航方向:   [{current_yaw_dir[0]:.3f}, {current_yaw_dir[1]:.3f}]"
        )
        print(
            f"  🎯 目标偏航方向:   [{target_yaw_dir[0]:.3f}, {target_yaw_dir[1]:.3f}]"
        )

    def print_control_command(self, action: np.ndarray):
        """
        Print control command vector by semantic order

        Args:
            action: 4维控制指令向量 [thrust, roll_rate, pitch_rate, yaw_rate]
        """
        if action is None:
            return
        if not self.cfg.debug.print_control:
            return

        # 解构控制指令向量
        thrust_raw = action[0]  # 原始推力指令 [-1, 1]
        roll_rate_raw = action[1]  # 原始横滚角速度指令 [-1, 1]
        pitch_rate_raw = action[2]  # 原始俯仰角速度指令 [-1, 1]
        yaw_rate_raw = action[3]  # 原始偏航角速度指令 [-1, 1]

        # 计算实际控制值
        thrust_acc = float(thrust_raw * 9.8 + 9.8)  # 转换为推力加速度
        roll_rate = roll_rate_raw * self._max_roll_pitch_rate  # 转换为横滚角速度
        pitch_rate = pitch_rate_raw * self._max_roll_pitch_rate  # 转换为俯仰角速度
        yaw_rate = yaw_rate_raw * self._max_yaw_rate  # 转换为偏航角速度

        print("🎮 控制指令 (4维):")
        print(f"  ⬆️  推力加速度:     {thrust_acc:.3f} m/s² (原始: {thrust_raw:.3f})")
        print(f"  🔄 横滚角速度:     {roll_rate:.3f} rad/s (原始: {roll_rate_raw:.3f})")
        print(
            f"  🔄 俯仰角速度:     {pitch_rate:.3f} rad/s (原始: {pitch_rate_raw:.3f})"
        )
        print(f"  🔄 偏航角速度:     {yaw_rate:.3f} rad/s (原始: {yaw_rate_raw:.3f})")

    def apply_obs_saturation(self, observation: np.ndarray) -> np.ndarray:
        if not self.cfg.control.input_saturation.enabled:
            return observation

        observation[6:9] = np.clip(
            observation[6:9],
            self.cfg.control.input_saturation.target_position[0],
            self.cfg.control.input_saturation.target_position[1],
        )

        return observation

    def run_inference(self, observation: np.ndarray) -> Optional[np.ndarray]:
        """运行神经网络推理"""
        try:
            action = self._policy_executor(observation)
            action = np.clip(action, -1.0, 1.0)
            return action

        except Exception as e:
            self.get_logger().error(f"推理错误: {e}")
            return None

    def publish_control_command(self, action: np.ndarray):
        """发布控制指令"""
        msg = VehicleThrustAccSetpoint()
        msg.timestamp = int(time.time() * 1e6)  # 微秒
        self._last_action = action.copy()
        action = action.clip(-1.0, 1.0)
        roll_rate = action[1] * self._max_roll_pitch_rate
        pitch_rate = action[2] * self._max_roll_pitch_rate
        yaw_rate = action[3] * self._max_yaw_rate

        rate_flu = np.array([roll_rate, pitch_rate, yaw_rate])
        rate_frd = frd_flu_rotate(rate_flu)

        # thrust_acc中 up 为正, 角速度则是 FRD系
        thrust_acc = float(action[0] * 9.81 + 9.81)
        msg.rates_sp[0] = rate_frd[0]
        msg.rates_sp[1] = rate_frd[1]
        msg.rates_sp[2] = rate_frd[2]
        if self.cfg.debug.acc_fixed:
            thrust_acc = 9.81
        msg.thrust_acc_sp = thrust_acc
        self._acc_rates_publisher.publish(msg)


@hydra.main(version_base="1.2", config_path="conf", config_name="pos_ctrl_config")
def main(cfg: DictConfig) -> int:
    """主函数"""
    rclpy.init()

    try:
        node = NeuralControlNode(cfg)
        if node._init_success:
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
        rclpy.shutdown()

    return 0


if __name__ == "__main__":
    main()
