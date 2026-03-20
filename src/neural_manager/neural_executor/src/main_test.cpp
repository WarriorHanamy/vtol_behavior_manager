/****************************************************************************
 * Copyright (c) 2025 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/

#include "rclcpp/rclcpp.hpp"

#include <neural_executor/test_executor.hpp>
#include <neural_executor/test_neural_manual_mode.hpp>
#include <neural_executor/test_executor_entry_mode.hpp>
#include <px4_ros2/components/node_with_mode.hpp>

using TestNeuralTaskNodeWithModeExecutor = px4_ros2::NodeWithModeExecutor<TestExecutor, TestExecutorEntryMode, TestNeuralManualMode>;

static const std::string kNodeName = "test_neural_executor";
static const bool kEnableDebugOutput = true;

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<TestNeuralTaskNodeWithModeExecutor>(kNodeName, kEnableDebugOutput));
  rclcpp::shutdown();
  return 0;
}
