#!/usr/bin/env python3

"""
Neural Demo Launch File

This launch file starts the Neural demo system with:
- Neural Demo Executor with integrated RC triggering
- Fake Network Node for trajectory generation
- Comprehensive failsafe mechanisms
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Get package directory
    pkg_dir = get_package_share_directory("neural_executor")

    # Declare launch arguments
    config_file_arg = DeclareLaunchArgument(
        "config_file",
        default_value=os.path.join(pkg_dir, "config", "demo.yaml"),
        description="Configuration file for demo targets and failsafe parameters",
    )

    debug_arg = DeclareLaunchArgument(
        "debug", default_value="false", description="Enable debug output"
    )

    common_params = {
        "config_file": LaunchConfiguration("config_file"),
        "neural_setpoint_timeout": 0.05,
        # don't use sim time when using px4 gazebo SITL
        "use_sim_time": False,
    }

    # Neural Demo Executor Node
    executor_node = Node(
        package="neural_executor",
        executable="neural_executor_node",
        name="neural_executor_node",
        output="screen",
        parameters=[common_params],
        emulate_tty=True,
        arguments=[
            "--ros-args",
            "--log-level",
            "info" if LaunchConfiguration("debug") == "false" else "debug",
            "--log-level",
            "rcl:=warn",
            "--log-level",
            "rmw_fastrtps_cpp:=warn",
        ],
    )

    return LaunchDescription([config_file_arg, debug_arg, executor_node])
