#!/usr/bin/env python3

"""
Test Neural Executor Launch File

This launch file starts the Test Neural Executor system with:
- Test Neural Executor Node using TestNeuralManualMode
- Configuration for waypoint-based trajectory control
- Comprehensive failsafe mechanisms
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
  pkg_dir = get_package_share_directory("neural_executor")

  config_file_arg = DeclareLaunchArgument(
    "config_file",
    default_value=os.path.join(pkg_dir, "config", "demo.yaml"),
    description="Configuration file for demo targets and failsafe parameters",
  )

  target_offset_arg = DeclareLaunchArgument(
    "target_offset",
    default_value="[0.0, 0.0, 0.0]",
    description="Target position offset as [x, y, z] in meters (body frame, z negative=up)",
  )

  common_params = {
    "config_file": LaunchConfiguration("config_file"),
    "neural_setpoint_timeout": 0.05,
    "use_sim_time": False,
    "target_offset": LaunchConfiguration("target_offset"),
  }

  executor_node = Node(
    package="neural_executor",
    executable="test_neural_executor_node",
    name="test_neural_executor_node",
    output="screen",
    parameters=[common_params],
    emulate_tty=True,
    arguments=[
      "--ros-args",
      "--log-level",
      "info",
      "--log-level",
      "rcl:=warn",
      "--log-level",
      "rmw_fastrtps_cpp:=warn",
    ],
  )

  return LaunchDescription([config_file_arg, target_offset_arg, executor_node])
