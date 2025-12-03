#!/usr/bin/env python3
"""
Copyright (c) 2025, Kousheek Chakraborty
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
import rclpy
import rclpy.node
import rclpy.qos
from px4_msgs.msg import VehicleRatesSetpoint, VehicleOdometry
from std_msgs.msg import Bool

from isaac_pos_ctrl_neural.math_utils import (
    quaternion_to_euler,
    rotation_matrix_ned_to_body,
    rotation_matrix_body_to_ned,
    quat_rotate_inverse,
)

try:
    import onnxruntime as ort

    ONNX_AVAILABLE = True
except ImportError as e:
    ONNX_AVAILABLE = False
    print(f"警告: ONNX依赖不可用: {e}")


class IsaacPositionControlNode(rclpy.node.Node):
    """Isaac位置控制神经网络推理节点"""

    def __init__(self):
        """初始化推理节点"""
        super().__init__("isaac_pos_ctrl_node", allow_undeclared_parameters=True)

        # 状态变量
        self._model_loaded = False
        self._inference_session = None
        self._active = False
        self._last_odom_sample_time = 0.0
        self._last_odom_receive_time = 0.0
        self._first_odom_received = False  # 标记是否收到第一帧
        self._last_action = np.array(
            [0.0, 0.0, 0.0, 0.0]
        )  # [throttle, roll_rate, pitch_rate, yaw_rate]
        self._target_position = np.array([0.0, 0.0, 1.5])  # NED坐标系 [x, y, z]
        self._target_yaw = 0.0  # 目标偏航角 (弧度)
        self._init_success = False

        # 接收间隔统计
        self._receive_interval_samples = []
        self._sample_interval_samples = []
        self._last_interval_report_time = 0.0
        self._interval_report_period = 5.0  # 每5秒报告一次平均间隔

        # 获取参数
        self.setup_parameters()
        self.load_parameters()

        # 初始化ONNX模型
        if self.init_model():
            # 创建发布者和订阅者
            self.init_publishers()
            self.init_subscribers()
            self.init_timers()

            self._init_success = True
            self.get_logger().info("🚀 Isaac位置控制节点初始化成功!")
        else:
            self.get_logger().error("❌ 模型初始化失败，节点无法启动")

    def setup_parameters(self):
        """设置ROS2参数"""
        # 模型参数
        self.declare_parameter(
            "model_path", "share/isaac_pos_ctrl_neural/models/isaac_pos_ctrl.onnx"
        )

        self.declare_parameter("control_rate", 50.0)

        # 目标参数
        self.declare_parameter("target_position", [0.0, 0.0, 1.5])

        self.declare_parameter("target_yaw", 0.0)

        # 控制限制参数
        self.declare_parameter("enable_input_saturation", True)

        # 角速度限制参数
        self.declare_parameter("max_roll_pitch_rate", 10.0)

        self.declare_parameter("max_yaw_rate", 5.0)

        # 调试参数
        self.declare_parameter("debug_mode", False)

    def load_parameters(self):
        """加载ROS2参数"""
        # 模型路径
        self._model_path = Path(self.get_parameter("model_path").value)

        # 控制参数
        self._control_rate = self.get_parameter("control_rate").value
        self._control_period = 1.0 / self._control_rate

        # 目标参数
        target_pos = self.get_parameter("target_position").value
        self._target_position = np.array(target_pos, dtype=np.float32)  # NED坐标系
        self._target_yaw = self.get_parameter("target_yaw").value

        # 其他参数
        self._enable_input_saturation = self.get_parameter(
            "enable_input_saturation"
        ).value
        self._debug_mode = self.get_parameter("debug_mode").value

        # 角速度限制参数
        self._max_roll_pitch_rate = self.get_parameter("max_roll_pitch_rate").value
        self._max_yaw_rate = self.get_parameter("max_yaw_rate").value

        self.get_logger().info("参数加载完成:")
        self.get_logger().info(f"  模型路径: {self._model_path}")
        self.get_logger().info(f"  控制频率: {self._control_rate:.1f} Hz")
        self.get_logger().info(f"  目标位置(NED): {self._target_position}")
        self.get_logger().info(f"  目标偏航: {math.degrees(self._target_yaw):.1f}°")
        self.get_logger().info(
            f"  最大横滚/俯仰角速度: {self._max_roll_pitch_rate:.1f} rad/s"
        )
        self.get_logger().info(f"  最大偏航角速度: {self._max_yaw_rate:.1f} rad/s")

    def init_model(self) -> bool:
        """初始化ONNX模型"""
        if not ONNX_AVAILABLE:
            self.get_logger().error("ONNX Runtime不可用，无法加载模型")
            return False

        try:
            # 检查模型文件
            if not self._model_path.exists():
                # 尝试在包共享目录中查找
                package_share = (
                    Path(__file__).parent.parent / "share" / "isaac_pos_ctrl_neural"
                )
                model_path = package_share / "models" / self._model_path.name
                if model_path.exists():
                    self._model_path = model_path
                else:
                    self.get_logger().error(f"模型文件不存在: {self._model_path}")
                    return False

            # 创建ONNX推理会话
            self.get_logger().info(f"加载ONNX模型: {self._model_path}")

            # GPU优先，如果可用则使用，否则CPU
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self._inference_session = ort.InferenceSession(
                str(self._model_path), providers=providers
            )

            # 获取模型输入输出信息
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

            # 验证输入形状 (应该为 [1, 20])
            if not (len(self._input_shape) == 2 and self._input_shape[1] == 20):
                self.get_logger().error(
                    f"输入形状不匹配，期望 [1, 20]，实际 {self._input_shape}"
                )
                return False

            # 验证输出形状 (应该为 [1, 4])
            if not (len(self._output_shape) == 2 and self._output_shape[1] == 4):
                self.get_logger().error(
                    f"输出形状不匹配，期望 [1, 4]，实际 {self._output_shape}"
                )
                return False

            self._model_loaded = True
            self.get_logger().info("✅ ONNX模型加载成功!")
            return True

        except Exception as e:
            self.get_logger().error(f"模型加载失败: {e}")
            return False

    def init_publishers(self):
        """初始化发布者"""
        # 控制指令发布者
        self._rates_publisher = self.create_publisher(
            VehicleRatesSetpoint, "/neural/rates_sp", 10
        )

        self._controller_heartbeat_publisher = self.create_publisher(
            Bool, "/neural/controller_heartbeat", 10
        )

        self.get_logger().info("发布者已初始化")

    def init_subscribers(self):
        """初始化订阅者"""
        # VehicleOdometry
        self._odometry_subscriber = self.create_subscription(
            VehicleOdometry,
            "/fmu/out/vehicle_odometry",
            self.odometry_callback,
            rclpy.qos.qos_profile_sensor_data,
        )

        self._mode_subscriber = self.create_subscription(
            Bool, "/neural/mode_neural_ctrl", self.mode_callback, 10
        )

        self.get_logger().info("订阅者已初始化")

    def init_timers(self):
        """初始化定时器"""
        # 控制发布定时器
        self._control_timer = self.create_timer(
            self._control_period, self.control_timer_callback
        )

        # 调试信息定时器 (每5秒打印一次状态)
        if self._debug_mode:
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
        if receive_interval > 50.0:  # 50ms超时
            self.get_logger().error(
                f"⚠️ 里程计接收间隔: {receive_interval:.1f} ms，数据过时"
            )
        else:
            # 记录正常的接收间隔用于统计
            self._receive_interval_samples.append(receive_interval)
            # 限制样本数量（保留最近100个）
            if len(self._receive_interval_samples) > 100:
                self._receive_interval_samples.pop(0)

        # 检查采样间隔超时
        if sample_interval > 50.0:  # 50ms超时
            self.get_logger().error(
                f"⚠️ 里程计采样间隔: {sample_interval:.1f} ms，数据过时"
            )
        else:
            # 记录正常的采样间隔用于统计
            self._sample_interval_samples.append(sample_interval)
            # 限制样本数量（保留最近100个）
            if len(self._sample_interval_samples) > 100:
                self._sample_interval_samples.pop(0)

        # 定期报告平均间隔
        current_time = time.time()
        if (
            current_time - self._last_interval_report_time
            >= self._interval_report_period
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

        # 转换为20维观测向量
        observation = self.process_odometry_to_observation(msg)

        if observation is None:
            self.get_logger().warn("观测数据处理失败")
            return

        # 执行神经网络推理（包含耗时计算）
        start_time = time.perf_counter()
        action = self.run_inference(observation)
        inference_time = (time.perf_counter() - start_time) * 1000.0  # 转换为毫秒

        if action is not None:
            # 更新上一时刻动作
            self._last_action = action

            # 立即发布控制指令
            self.publish_control_command(self._last_action)

            # 输出推理耗时
            self.get_logger().info(f"🧠 神经网络推理耗时: {inference_time:.2f} ms")

            # self._last_odom_sample_time = msg.timestamp_sample

    def mode_callback(self, msg: Bool):
        was_active = self._active
        self._active = msg.data

        if not was_active and self._active:
            self.get_logger().warn("🧠 启用神经网络控制模式")
            # 重置状态
            self._last_action = np.array([0.0, 0.0, 0.0, 0.0])
        elif was_active and not self._active:
            self.get_logger().warn("🛑 停用神经网络控制模式")
            # 发布停止控制指令
            self.publish_stop_command()

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
        self.get_logger().info(f"  当前动作: {self._last_action}")

    def process_odometry_to_observation(
        self, msg: VehicleOdometry
    ) -> Optional[np.ndarray]:
        """
        将VehicleOdometry转换为20维观测向量

        基于drone_pos_ctrl_env_cfg.py的Policy输入结构：
        1. lin_vel (3维): [vx, vy, vz]
        2. projected_gravity_b (3维): [gx, gy, gz]
        3. ang_vel (3维): [wx, wy, wz]
        4. current_yaw_direction (2维): [cos(yaw), sin(yaw)]
        5. target_pos_b (3维): 目标位置(机体坐标系)
        6. target_yaw (2维): 目标偏航方向
        7. actions (4维): 上一时刻动作

        Args:
            msg: VehicleOdometry消息

        Returns:
            20维观测向量或None(数据无效时)
        """
        try:
            # 提取基本状态
            position = np.array(msg.position, dtype=np.float32)  # NED坐标系 [x, y, z]
            velocity = np.array(
                msg.velocity, dtype=np.float32
            )  # 参考frame [vx, vy, vz]
            angular_velocity = np.array(
                msg.angular_velocity, dtype=np.float32
            )  # 机体frame [wx, wy, wz]
            quaternion = np.array(msg.q, dtype=np.float32)  # [w, x, y, z] Hamilton约定

            # 1. lin_vel (3维) - 转换为机体坐标系
            if msg.velocity_frame == msg.VELOCITY_FRAME_NED:
                # NED到机体坐标系的转换 (忽略滚动和俯仰的小角度假设)
                roll, pitch, yaw = quaternion_to_euler(quaternion)

                # 旋转矩阵 (NED到机体)
                R = rotation_matrix_ned_to_body(roll, pitch, yaw)
                lin_vel_b = R @ velocity
            elif msg.velocity_frame == msg.VELOCITY_FRAME_BODY_FRD:
                lin_vel_b = velocity
            else:
                self.get_logger().warn(f"未知的速度frame: {msg.velocity_frame}")
                return None

            # 2. projected_gravity_b (3维) - 在机体坐标系中的重力投影
            # 在NED坐标系中重力为[0, 0, 9.81]，在机体坐标系中的投影
            gravity_world = np.array([0.0, 0.0, 9.81])  # NED坐标系的向上重力
            gravity_b = R @ gravity_world  # 转换到机体坐标系
            gravity_b_normalized = gravity_b / 9.81  # 归一化

            # 3. ang_vel (3维) - 已经在机体坐标系中
            ang_vel_b = angular_velocity

            # 4. current_yaw_direction (2维) - 机体x轴在世界水平面的投影方向
            # 获取机体到世界的旋转矩阵
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

            # 5. target_pos_b (3维) - 目标位置在机体坐标系中的向量
            # 计算世界坐标系到机体坐标系的变换
            target_world = self._target_position
            current_world = position
            to_target = target_world - current_world

            # 使用四元数旋转向量到机体坐标系 (注意四元数约定)
            target_pos_b = quat_rotate_inverse(quaternion, to_target)

            # 6. target_yaw (2维) - 目标偏航方向的单位向量
            target_yaw_dir = np.array(
                [math.cos(self._target_yaw), math.sin(self._target_yaw)]
            )

            # 7. actions (4维) - 上一时刻的动作
            prev_actions = self._last_action

            # 组装20维观测向量
            observation = np.concatenate(
                [
                    lin_vel_b,  # 3维: 机体线速度 [vx, vy, vz]
                    gravity_b_normalized,  # 3维: 机体重力投影 [gx, gy, gz]
                    ang_vel_b,  # 3维: 机体角速度 [wx, wy, wz]
                    current_yaw_dir,  # 2维: 当前偏航方向 [cos(yaw), sin(yaw)]
                    target_pos_b,  # 3维: 目标位置(机体) [dx, dy, dz]
                    target_yaw_dir,  # 2维: 目标偏航方向 [cos(target_yaw), sin(target_yaw)]
                    prev_actions,  # 4维: 上一时刻动作 [throttle, roll_rate, pitch_rate, yaw_rate]
                ],
                dtype=np.float32,
            )

            # 应用输入饱和限制
            if self._enable_input_saturation:
                observation = self.apply_input_saturation(observation)

            return observation

        except Exception as e:
            self.get_logger().error(f"观测处理错误: {e}")
            return None

    def apply_input_saturation(self, observation: np.ndarray) -> np.ndarray:
        """应用输入饱和限制以防止数值不稳定"""
        # 线速度限制 (±10 m/s)
        observation[0:3] = np.clip(observation[0:3], -10.0, 10.0)

        # 重力投影限制 (±1.0，归一化后)
        observation[3:6] = np.clip(observation[3:6], -1.0, 1.0)

        # 角速度限制 (±20 rad/s)
        observation[6:9] = np.clip(observation[6:9], -20.0, 20.0)

        # 当前水平yaw向量已经归一化 [-1, 1]
        observation[9:11] = np.clip(observation[9:11], -1.0, 1.0)

        # 目标位置向量限制 (±10 m) 符合isaac中训练范围
        observation[11:14] = np.clip(observation[11:14], -10.0, 10.0)

        # 目标水平yaw向量已经归一化 [-1, 1]
        observation[14:16] = np.clip(observation[14:16], -1.0, 1.0)

        # 动作限制 [-1, 1]
        observation[16:20] = np.clip(observation[16:20], -1.0, 1.0)

        return observation

    def run_inference(self, observation: np.ndarray) -> Optional[np.ndarray]:
        """运行神经网络推理"""
        try:
            # 准备输入数据
            input_data = observation.reshape(1, -1).astype(np.float32)

            # ONNX推理
            ort_inputs = {self._input_name: input_data}
            ort_outputs = self._inference_session.run(None, ort_inputs)

            # 提取输出
            action = ort_outputs[0][0]  # 形状 (4,)

            # 应用输出饱和限制
            action = np.clip(action, -1.0, 1.0)

            return action

        except Exception as e:
            self.get_logger().error(f"推理错误: {e}")
            return None

    def publish_control_command(self, action: np.ndarray):
        """发布控制指令"""
        try:
            msg = VehicleRatesSetpoint()
            msg.timestamp = int(time.time() * 1e6)  # 微秒

            # 映射动作输出到PX4控制范围
            # action[0]: throttle [-1, 1] → throttle [0, 1]
            throttle = (action[0] + 1.0) / 2.0  # 映射到[0, 1]
            throttle = np.clip(throttle, 0.0, 1.0)

            # action[1:3]: roll/pitch rate [-1, 1] → rate [-max_roll_pitch_rate, max_roll_pitch_rate] rad/s
            roll_rate = action[1] * self._max_roll_pitch_rate
            pitch_rate = action[2] * self._max_roll_pitch_rate

            # action[3]: yaw rate [-1, 1] → rate [-max_yaw_rate, max_yaw_rate] rad/s
            yaw_rate = action[3] * self._max_yaw_rate

            # 设置消息字段
            msg.roll = float(roll_rate)
            msg.pitch = float(pitch_rate)
            msg.yaw = float(yaw_rate)

            # 检查throttle的值
            # self.get_logger().warn(f"计算的油门值: {throttle:.3f}")

            # 推力向量: [thrust_x, thrust_y, thrust_z] 在机体NED坐标系
            msg.thrust_body[0] = 0.0
            msg.thrust_body[1] = 0.0
            msg.thrust_body[2] = -throttle
            msg.reset_integral = False

            self._rates_publisher.publish(msg)

            if self._debug_mode:
                self.get_logger().debug(
                    f"控制指令: 油门={throttle:.3f}, "
                    f"俯仰={pitch_rate:.3f}, 横滚={roll_rate:.3f}, 偏航={yaw_rate:.3f}"
                )

        except Exception as e:
            self.get_logger().error(f"控制指令发布错误: {e}")

    def publish_stop_command(self):
        """发布停止控制指令"""
        try:
            msg = VehicleRatesSetpoint()
            msg.timestamp = int(time.time() * 1e6)
            msg.roll = 0.0
            msg.pitch = 0.0
            msg.yaw = 0.0
            msg.thrust_body[0] = 0.0
            msg.thrust_body[1] = 0.0
            msg.thrust_body[2] = 0.0
            msg.reset_integral = False

            self._rates_publisher.publish(msg)
            self.get_logger().info("发布停止控制指令")

        except Exception as e:
            self.get_logger().error(f"停止指令发布错误: {e}")


def main(args=None):
    """主函数"""
    rclpy.init(args=args)

    try:
        node = IsaacPositionControlNode()

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
    import sys

    sys.exit(main())
