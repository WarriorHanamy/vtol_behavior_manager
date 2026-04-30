#!/usr/bin/env python3

"""Neural Gate Mode Switch Launch File

Starts the neural_gate node which implements a mode-switch state machine
based on PX4 VehicleStatus. Publishes /neural/target in POSCTL mode and
sends offboard mode commands on RC trigger. Offboard heartbeat sent at 10Hz.

Usage:
  ros2 launch neural_gate neural_gate.launch.py task:=hover
  ros2 launch neural_gate neural_gate.launch.py task:=acro
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node

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

  return LaunchDescription(
    [
      task_arg,
      gate_hover,
      gate_acro,
    ]
  )
