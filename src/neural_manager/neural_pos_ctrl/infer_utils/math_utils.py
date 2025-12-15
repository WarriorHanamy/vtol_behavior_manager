"""
Copyright (c) 2025, Differential Robotics
All rights reserved.

SPDX-License-Identifier: BSD-3-Clause

数学工具模块

该模块提供四元数、欧拉角和旋转矩阵相关的数学计算函数，
便于在多个ROS2功能包中复用。

主要功能：
1. 四元数与欧拉角转换
2. 旋转矩阵计算
3. 四元数运算
4. 向量旋转
"""

from __future__ import annotations

import math
from typing import Tuple

import numpy as np


def quaternion_to_euler(q: np.ndarray) -> Tuple[float, float, float]:
    """
    四元数转换为欧拉角 (roll, pitch, yaw)

    使用Hamilton四元数约定 [w, x, y, z]

    Args:
        q: 四元数 [w, x, y, z]

    Returns:
        欧拉角元组 (roll, pitch, yaw) 单位：弧度
    """
    # Hamilton约定四元数 [w, x, y, z]
    w, x, y, z = q[0], q[1], q[2], q[3]

    # 欧拉角转换
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(np.clip(2 * (w * y - z * x), -1, 1))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))

    return roll, pitch, yaw


def euler_to_quaternion(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """
    欧拉角转换为四元数，内旋顺序ZYX (yaw-pitch-roll)

    Args:
        yaw: 偏航角 (弧度)
        pitch: 俯仰角 (弧度)
        roll: 横滚角 (弧度)

    Returns:
        四元数 [w, x, y, z] (Hamilton约定)
    """
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy

    return np.array([w, x, y, z])


def rotation_matrix_ned_to_body(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """
    计算NED到机体坐标系的旋转矩阵

    使用ZYX旋转序列 (先绕Z转yaw，再绕Y转pitch，最后绕X转roll)

    Args:
        roll: 横滚角 (弧度)
        pitch: 俯仰角 (弧度)
        yaw: 偏航角 (弧度)

    Returns:
        3x3旋转矩阵
    """
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    # ZYX旋转序列
    R = np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ]
    )
    return R


def rotation_matrix_body_to_ned(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """
    计算机体到NED坐标系的旋转矩阵

    这是NED到机体旋转矩阵的转置

    Args:
        roll: 横滚角 (弧度)
        pitch: 俯仰角 (弧度)
        yaw: 偏航角 (弧度)

    Returns:
        3x3旋转矩阵
    """
    # 机体到世界的旋转矩阵是NED到机体旋转矩阵的转置
    R_ned_to_body = rotation_matrix_ned_to_body(roll, pitch, yaw)
    return R_ned_to_body.T


def quaternion_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """
    四元数乘法 (Hamilton约定)

    Args:
        q1: 第一个四元数 [w1, x1, y1, z1]
        q2: 第二个四元数 [w2, x2, y2, z2]

    Returns:
        四元数乘积 [w, x, y, z]
    """
    w1, x1, y1, z1 = q1[0], q1[1], q1[2], q1[3]
    w2, x2, y2, z2 = q2[0], q2[1], q2[2], q2[3]

    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2

    return np.array([w, x, y, z])


def quat_act_rot(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """
    使用四元数旋转向量

    q * v * q_conj，其中v作为纯四元数[0, vx, vy, vz]

    Args:
        q: 四元数 [w, x, y, z] (Hamilton约定)
        v: 三维向量 [vx, vy, vz]

    Returns:
        旋转后的向量
    """
    w, u = q[0], q[1:4]

    uv = np.cross(u, v)
    uuv = np.cross(u, uv)
    return v + 2.0 * (w * uv + uuv)


def quat_pas_rot(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """
    被动旋转，坐标系变化，读数变化

    q_conj * v * q，其中v作为纯四元数[0, vx, vy, vz]

    Args:
        q: 四元数 [w, x, y, z] (Hamilton约定)
        v: 三维向量 [vx, vy, vz]

    Returns:
        旋转后的向量
    """
    q = q.conj()
    w, u = q[0], q[1:4]

    uv = np.cross(u, v)
    uuv = np.cross(u, uv)
    return v + 2 * (w * uv + uuv)


def quat_right_multiply_flu_frd(q: np.ndarray) -> np.ndarray:
    """对齐FLU与FRD坐标系"""
    q_flu_frd = np.array([0.0, 1.0, 0.0, 0.0])
    rtn_q = quaternion_multiply(q, q_flu_frd)
    return normalize_quaternion(rtn_q)


def frd_flu_rotate(v: np.ndarray) -> np.ndarray:
    """对齐FRD与FLU坐标系的向量"""
    q_flu_frd = np.array([0.0, 1.0, 0.0, 0.0])
    return quat_act_rot(q_flu_frd, v)


def normalize_quaternion(q: np.ndarray) -> np.ndarray:
    """
    归一化四元数

    Args:
        q: 四元数 [w, x, y, z]

    Returns:
        归一化后的四元数
    """
    norm = np.linalg.norm(q)
    if norm > 1e-10:
        return q / norm
    else:
        # 零四元数返回单位四元数
        return np.array([1.0, 0.0, 0.0, 0.0])


def quaternion_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """
    四元数转换为旋转矩阵

    Args:
        q: 四元数 [w, x, y, z] (Hamilton约定)

    Returns:
        3x3旋转矩阵
    """
    q = normalize_quaternion(q)
    w, x, y, z = q[0], q[1], q[2], q[3]

    R = np.array(
        [
            [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * z * w, 2 * x * z + 2 * y * w],
            [2 * x * y + 2 * z * w, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * x * w],
            [2 * x * z - 2 * y * w, 2 * y * z + 2 * x * w, 1 - 2 * x * x - 2 * y * y],
        ]
    )

    return R


def rotation_matrix_to_quaternion(R: np.ndarray) -> np.ndarray:
    """
    旋转矩阵转换为四元数

    Args:
        R: 3x3旋转矩阵

    Returns:
        四元数 [w, x, y, z] (Hamilton约定)
    """
    # 计算四元数分量
    trace = np.trace(R)

    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    else:
        if R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
            w = (R[2, 1] - R[1, 2]) / s
            x = 0.25 * s
            y = (R[0, 1] + R[1, 0]) / s
            z = (R[0, 2] + R[2, 0]) / s
        elif R[1, 1] > R[2, 2]:
            s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
            w = (R[0, 2] - R[2, 0]) / s
            x = (R[0, 1] + R[1, 0]) / s
            y = 0.25 * s
            z = (R[1, 2] + R[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
            w = (R[1, 0] - R[0, 1]) / s
            x = (R[0, 2] + R[2, 0]) / s
            y = (R[1, 2] + R[2, 1]) / s
            z = 0.25 * s

    return np.array([w, x, y, z])
