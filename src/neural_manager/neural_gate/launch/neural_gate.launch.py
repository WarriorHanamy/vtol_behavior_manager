#!/usr/bin/env python3

"""Neural Gate Launch File

Starts the Neural Gate node with configurable parameters.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
  target_offset_arg = DeclareLaunchArgument(
    "target_offset",
    default_value="[0.0, 0.0, 0.0]",
    description="Target position offset as [x, y, z] in meters",
  )

  common_params = {
    "use_sim_time": False,
    "trigger_source": "aux1",
    "button_mask": 1024,
    "aux1_on_threshold": 0.6,
    "aux1_off_threshold": 0.4,
    "neural_control_timeout_s": 0.5,
    "target_offset": LaunchConfiguration("target_offset"),
  }

  gate_node = Node(
    package="neural_gate",
    executable="neural_gate_node",
    name="neural_gate_node",
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

  return LaunchDescription([target_offset_arg, gate_node])
