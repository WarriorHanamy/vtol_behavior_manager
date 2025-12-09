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
from typing import Optional

import numpy as np
from omegaconf.omegaconf import OmegaConf, DictConfig
import hydra
import rclpy
import rclpy.node
import rclpy.qos
from px4_msgs.msg import VehicleThrustAccSetpoint, VehicleOdometry
from std_msgs.msg import Bool

from math_utils import (
    quaternion_to_euler,
    rotation_matrix_ned_to_body,
    rotation_matrix_body_to_ned,
    quat_rotate_inverse,
)

import onnxruntime as ort


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
        self._target_position = np.array(cfg.target.position, dtype=np.float32)  # NED坐标系
        self._target_yaw = cfg.target.yaw
        self._max_roll_pitch_rate = cfg.control.max_roll_pitch_rate
        self._max_yaw_rate = cfg.control.max_yaw_rate

        # Log loaded configuration
        self.get_logger().info("Hydra配置加载完成:")
        self.get_logger().info(f"  模型路径: {self._model_path}")
        self.get_logger().info(f"  控制频率: {self._control_rate:.1f} Hz")
        self.get_logger().info(f"  目标位置(NED): {self._target_position}")
        self.get_logger().info(f"  目标偏航: {math.degrees(self._target_yaw):.1f}°")
        self.get_logger().info(
            f"  最大横滚/俯仰角速度: {self._max_roll_pitch_rate:.1f} rad/s"
        )
        self.get_logger().info(f"  最大偏航角速度: {self._max_yaw_rate:.1f} rad/s")

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

        providers = self.cfg.model.inference.providers
        self._inference_session = ort.InferenceSession(
            str(self._model_path), providers=providers
        )

        input_info = self._inference_session.get_inputs()[0]
        output_info = self._inference_session.get_outputs()[0]

        self._input_name = input_info.name
        self._output_name = output_info.name
        self._input_shape = input_info.shape
        self._output_shape = output_info.shape

        self.get_logger().info("模型信息:")
        self.get_logger().info(
            f"  输入: {self._input_name}, 形状: {self._input_shape}"
        )
        self.get_logger().info(
            f"  输出: {self._output_name}, 形状: {self._output_shape}"
        )

        # 验证输入形状
        expected_input_shape = [1, 16]
        expected_output_shape = [1, 4]

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
        return True



    def init_publishers(self):
        """初始化发布者"""
        # 控制指令发布者
        self._acc_rates_publisher = self.create_publisher(
            VehicleThrustAccSetpoint,
            self.cfg.node.setpoint_topic,
            1
        )

        self._controller_heartbeat_publisher = self.create_publisher(
            Bool,
            self.cfg.node.heartbeat_topic,
            10
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

        # self._mode_subscriber = self.create_subscription(
        #     Bool,
        #     self.cfg.node.mode_topic,
        #     self.mode_callback,
        #     10
        # )

        self.get_logger().info("订阅者已初始化")

    def init_timers(self):
        """初始化定时器"""
        # 控制发布定时器
        self._control_timer = self.create_timer(
            self._control_period, self.control_timer_callback
        )

        self._debug_timer = self.create_timer(
            5.0,
            self.debug_callback
        )

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
        if (
            current_time - self._last_interval_report_time
            >= 5.0
        ):
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
            # 立即发布控制指令
            self.publish_control_command(action)
            # 输出推理耗时（如果启用性能监控）
            if self.cfg.debug.measure_inference_time:
                self.get_logger().info(f"🧠 神经网络推理耗时: {inference_time:.2f} ms")

    def mode_callback(self, msg: Bool):
        was_active = self._active
        self._active = msg.data
        if not was_active and self._active:
            self.get_logger().warn("🧠 启用神经网络控制模式")

    def control_timer_callback(self):
        heartbeat_msg = Bool()
        heartbeat_msg.data = True
        self._controller_heartbeat_publisher.publish(heartbeat_msg)

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
        try:
            position = np.array(msg.position, dtype=np.float32)  # NED坐标系 [x, y, z]
            velocity = np.array(
                msg.velocity, dtype=np.float32
            )  # 参考frame [vx, vy, vz]
            angular_velocity = np.array(
                msg.angular_velocity, dtype=np.float32
            )  # 机体frame [wx, wy, wz]
            quaternion = np.array(msg.q, dtype=np.float32)  # [w, x, y, z] Hamilton约定

            # Assuming msg.velocity_frame == msg.VELOCITY_FRAME_NED:
            roll, pitch, yaw = quaternion_to_euler(quaternion)
            rot_mat = rotation_matrix_ned_to_body(roll, pitch, yaw)
            lin_vel_b = rot_mat @ velocity
            # 在NED坐标系中重力为[0, 0, 9.81]，在机体坐标系中的投影
            gravity_world = np.array([0.0, 0.0, 9.81])  # NED坐标系的向上重力
            gravity_b = rot_mat @ gravity_world  # 转换到机体坐标系
            gra_dir_b = gravity_b / 9.81  # 归一化

            # 3. ang_vel (3维) - 已经在机体坐标系中
            ang_vel_b = angular_velocity

            roll, pitch, yaw = quaternion_to_euler(quaternion)
            R_body_to_world = rotation_matrix_body_to_ned(roll, pitch, yaw)

            # 机体x轴在世界坐标系中的方向
            body_x_world = R_body_to_world @ np.array([1.0, 0.0, 0.0])

            # 投影到水平面（去除z分量）并归一化
            body_x_horizontal = body_x_world[:2]  # 只取x, y分量
            norm = np.linalg.norm(body_x_horizontal)
            if norm > 1e-6:  # 避免除零
                current_yaw_dir = body_x_horizontal / norm
            else:
                # 如果几乎垂直，使用原方法作为fallback
                current_yaw_dir = np.array([math.cos(yaw), math.sin(yaw)])

            target_world = self._target_position
            current_world = position
            to_target = target_world - current_world

            to_target_pos_b = quat_rotate_inverse(quaternion, to_target)

            target_yaw_dir = np.array(
                [math.cos(self._target_yaw), math.sin(self._target_yaw)]
            )

            observation = np.concatenate(
                [
                    to_target_pos_b,  # 3维: 目标位置(机体) [dx, dy, dz]
                    lin_vel_b,  # 3维: 机体线速度 [vx, vy, vz]
                    ang_vel_b,  # 3维: 机体角速度 [wx, wy, wz]
                    gra_dir_b,  # 3维: 机体重力投影 [gx, gy, gz]
                    current_yaw_dir,  # 2维: 当前偏航方向 [cos(yaw), sin(yaw)]
                    target_yaw_dir,  # 2维: 目标偏航方向 [cos(target_yaw), sin(target_yaw)]
                ],
                dtype=np.float32,
            )

            # 应用输入饱和限制
            observation = self.apply_input_saturation(observation)

            return observation

        except Exception as e:
            self.get_logger().error(f"观测处理错误: {e}")
            return None

    def print_observation(self, observation: np.ndarray):
        """
        Print observation vector by semantic order

        Args:
            observation: 16维观测向量
        """
        if observation is None:
            return

        # 解构观测向量
        to_target_pos_b = observation[0:3]  # 目标位置(机体)
        lin_vel_b = observation[3:6]        # 机体线速度
        ang_vel_b = observation[6:9]        # 机体角速度
        gra_dir_b = observation[9:12]       # 机体重力投影
        current_yaw_dir = observation[12:14] # 当前偏航方向
        target_yaw_dir = observation[14:16]  # 目标偏航方向

        print("📊 观测向量 (16维):")
        print(f"  🎯 目标位置(机体): [{to_target_pos_b[0]:.3f}, {to_target_pos_b[1]:.3f}, {to_target_pos_b[2]:.3f}]")
        print(f"  🚁 机体线速度:     [{lin_vel_b[0]:.3f}, {lin_vel_b[1]:.3f}, {lin_vel_b[2]:.3f}]")
        print(f"  🔄 机体角速度:     [{ang_vel_b[0]:.3f}, {ang_vel_b[1]:.3f}, {ang_vel_b[2]:.3f}]")
        print(f"  🌍 重力投影:       [{gra_dir_b[0]:.3f}, {gra_dir_b[1]:.3f}, {gra_dir_b[2]:.3f}]")
        print(f"  🧭 当前偏航方向:   [{current_yaw_dir[0]:.3f}, {current_yaw_dir[1]:.3f}]")
        print(f"  🎯 目标偏航方向:   [{target_yaw_dir[0]:.3f}, {target_yaw_dir[1]:.3f}]")

    def apply_input_saturation(self, observation: np.ndarray) -> np.ndarray:
        if not self.cfg.control.input_saturation.enabled:
            return observation

        observation[0:3] = np.clip(
            observation[0:3],
            self.cfg.control.input_saturation.linear_velocity[0],
            self.cfg.control.input_saturation.linear_velocity[1]
        )

        # 角速度限制
        observation[6:9] = np.clip(
            observation[6:9],
            self.cfg.control.input_saturation.angular_velocity[0],
            self.cfg.control.input_saturation.angular_velocity[1]
        )

        # 目标位置向量限制
        observation[11:14] = np.clip(
            observation[11:14],
            self.cfg.control.input_saturation.target_position[0],
            self.cfg.control.input_saturation.target_position[1]
        )


        return observation

    def run_inference(self, observation: np.ndarray) -> Optional[np.ndarray]:
        """运行神经网络推理"""
        try:
            input_data = observation.reshape(1, -1).astype(np.float32)

            ort_inputs = {self._input_name: input_data}
            ort_outputs = self._inference_session.run(
                [self._output_name], ort_inputs
            )

            action = ort_outputs[0][0]
            action = np.clip(action, -1.0, 1.0)

            return action

        except Exception as e:
            self.get_logger().error(f"推理错误: {e}")
            return None

    def publish_control_command(self, action: np.ndarray):
        """发布控制指令"""
        msg = VehicleThrustAccSetpoint()
        msg.timestamp = int(time.time() * 1e6)  # 微秒
        action = action.clip(-1.0, 1.0)
        roll_rate = action[1] * self._max_roll_pitch_rate
        pitch_rate = action[2] * self._max_roll_pitch_rate
        yaw_rate = action[3] * self._max_yaw_rate

        thrust_acc = float(action[0] * 19.6 + 9.8)
        # 设置消息字段
        msg.rates_sp[0] = roll_rate
        msg.rates_sp[1] = pitch_rate
        msg.rates_sp[2] = yaw_rate
        msg.thrust_acc_sp = thrust_acc
        self._acc_rates_publisher.publish(msg)


@hydra.main(
    version_base="1.2",
    config_path="conf",
    config_name="pos_ctrl_config"
)
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
