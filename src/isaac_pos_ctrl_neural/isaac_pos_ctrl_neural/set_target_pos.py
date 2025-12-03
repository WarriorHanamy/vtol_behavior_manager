#!/usr/bin/env python3
"""
Copyright (c) 2025, Kousheek Chakraborty
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

设置目标位置工具

该工具提供命令行接口来设置Isaac位置控制节点的目标位置。
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import List

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Header

from .math_utils import euler_to_quaternion


class TargetPositionSetter(Node):
    """目标位置设置节点"""

    def __init__(
        self, position: List[float], yaw: float = 0.0, frame_id: str = "world"
    ):
        """
        初始化目标设置节点

        Args:
            position: 目标位置 [x, y, z] in NED meters
            yaw: 目标偏航角 (radians)
            frame_id: 坐标系ID
        """
        super().__init__("set_target_pos")

        if len(position) != 3:
            self.get_logger().error(f"位置参数必须有3个元素，得到 {len(position)}")
            sys.exit(1)

        self._target_position = position
        self._target_yaw = yaw
        self._frame_id = frame_id

        # 创建发布者
        self._target_pose_publisher = self.create_publisher(
            PoseStamped, "/neural/target_pose", 10
        )

        self.get_logger().info("目标位置设置工具已初始化:")
        self.get_logger().info(
            f"  位置(NED): {position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f}"
        )
        self.get_logger().info(f"  偏航角: {math.degrees(yaw):.1f}°")
        self.get_logger().info(f"  坐标系: {frame_id}")

    def publish_target(self):
        """发布目标位置"""
        # 创建PoseStamped消息
        msg = PoseStamped()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id

        # 设置位置 (NED坐标系)
        msg.pose.position.x = self._target_position[0]  # 北向
        msg.pose.position.y = self._target_position[1]  # 东向
        msg.pose.position.z = self._target_position[2]  # 地下

        # 设置姿态 (仅偏航，无滚动和俯仰)
        # 使用math_utils中的euler_to_quaternion函数
        quaternion = euler_to_quaternion(
            0.0, 0.0, self._target_yaw
        )  # roll=0, pitch=0, yaw=target_yaw
        msg.pose.orientation.w = quaternion[0]
        msg.pose.orientation.x = quaternion[1]
        msg.pose.orientation.y = quaternion[2]
        msg.pose.orientation.z = quaternion[3]

        # 发布消息
        self._target_pose_publisher.publish(msg)
        self.get_logger().info("目标位置已发布")

    def run(self):
        """运行发布器"""
        try:
            self.publish_target()
            self.get_logger().info("目标位置设置完成，节点退出")
        except Exception as e:
            self.get_logger().error(f"发布目标位置失败: {e}")


def parse_position_string(pos_str: str) -> List[float]:
    """解析位置字符串为浮点数列表"""
    try:
        # 移除方括号并分割
        pos_str = pos_str.strip()
        if pos_str.startswith("[") and pos_str.endswith("]"):
            pos_str = pos_str[1:-1]

        # 分割并转换为浮点数
        positions = [float(x.strip()) for x in pos_str.split(",")]
        return positions
    except ValueError as e:
        print(f"位置解析错误: {e}")
        print("期望格式: [x, y, z] 或 x,y,z")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="设置Isaac位置控制节点的目标位置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 设置2D位置 (默认高度1.5m，偏航0°)
  python3 set_target_pos.py --position 2.0,1.0

  # 设置3D位置和偏航角
  python3 set_target_pos.py --position 2.0,1.0,2.5 --yaw 1.57

  # 使用不同坐标系
  python3 set_target_pos.py --position 2.0,1.0,2.5 --frame-id "ned"

注意：
  - 位置使用NED坐标系 (北-东-地)
  - 偏航角为弧度 (逆时针为正)
  - 目标位置由neural_demo功能包处理
        """,
    )

    parser.add_argument(
        "--position",
        "-p",
        type=str,
        required=True,
        help='目标位置 [x, y, z] 或 "x, y, z" (NED坐标系，单位：米)',
    )

    parser.add_argument(
        "--yaw", "-y", type=float, default=0.0, help="目标偏航角 (弧度，默认: 0.0)"
    )

    parser.add_argument(
        "--frame-id", "-f", type=str, default="world", help='坐标系ID (默认: "world")'
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="启用详细输出")

    args = parser.parse_args()

    # 解析位置参数
    position = parse_position_string(args.position)
    if position is None or len(position) != 3:
        print("错误: 无效的位置参数")
        parser.print_help()
        sys.exit(1)

    # 初始化ROS2
    rclpy.init(args=args)

    try:
        # 创建目标设置节点
        node = TargetPositionSetter(
            position=position, yaw=args.yaw, frame_id=args.frame_id
        )

        if args.verbose:
            node.get_logger().set_level(rclpy.logging.LoggingSeverity.DEBUG)

        # 运行发布器
        node.run()

    except KeyboardInterrupt:
        print("用户中断")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
