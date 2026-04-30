#!/usr/bin/env python3

"""Unified Neural Gate + Inference Launch File

Starts:
  - Gate node (hover or acro, selected by 'task' argument)
  - Inference node (LifecycleNode, starts unconfigured)
  - Lifecycle configure command (2s delay)
  - Activation watcher (2.5s delay, triggers activate on first target)

Usage:
  ros2 launch neural_inference neural_gate.launch.py task:=hover
  ros2 launch neural_inference neural_gate.launch.py task:=acro
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import LifecycleNode, Node

LOG_ARGS = [
  "--ros-args",
  "--log-level",
  "info",
  "--log-level",
  "rcl:=warn",
  "--log-level",
  "rmw_fastrtps_cpp:=warn",
]


def generate_launch_description():
  task_arg = DeclareLaunchArgument(
    "task",
    default_value="hover",
    description="Task to run: 'hover' or 'acro'",
  )

  is_hover = PythonExpression(["'", LaunchConfiguration("task"), "' == 'hover'"])
  is_acro = PythonExpression(["'", LaunchConfiguration("task"), "' == 'acro'"])

  # Gate node (one of them, based on task)
  gate_hover = Node(
    package="neural_gate",
    executable="neural_gate_hover",
    name="neural_gate",
    output="screen",
    emulate_tty=True,
    condition=IfCondition(is_hover),
    arguments=LOG_ARGS,
  )

  gate_acro = Node(
    package="neural_gate",
    executable="neural_gate_acro",
    name="neural_gate",
    output="screen",
    emulate_tty=True,
    condition=IfCondition(is_acro),
    arguments=LOG_ARGS,
  )

  # Inference node — LifecycleNode, starts unconfigured
  params_file = os.path.join(os.path.dirname(__file__), "..", "config", "neural_infer_params.yaml")
  infer_node = LifecycleNode(
    package="neural_inference",
    executable="neural_infer_node",
    name="neural_infer_node",
    namespace="",
    output="screen",
    parameters=[params_file],
    arguments=LOG_ARGS,
  )

  # Step 1: configure after 2s (give node time to start)
  configure_cmd = ExecuteProcess(
    cmd=["ros2", "lifecycle", "set", "/neural_infer_node", "configure"],
    output="screen",
  )

  # Step 2: watcher after 2.5s (waits for /neural/target to activate)
  watcher = Node(
    package="neural_inference",
    executable="neural_activation_watcher",
    name="neural_activation_watcher",
    output="screen",
  )

  return LaunchDescription(
    [
      task_arg,
      gate_hover,
      gate_acro,
      infer_node,
      TimerAction(period=2.0, actions=[configure_cmd]),
      TimerAction(period=2.5, actions=[watcher]),
    ]
  )
