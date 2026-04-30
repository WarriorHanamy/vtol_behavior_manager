// Copyright (c) 2025, Differential Robotics
// All rights reserved.
// SPDX-License-Identifier: BSD-3-Clause
//
// Neural Gate — Hover variant

#include "neural_gate_common.hpp"

int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);

  NeuralGateConfig cfg;
  cfg.task_type = goal_msgs::msg::NeuralTarget::TASK_HOVER;

  rclcpp::spin(std::make_shared<NeuralGateNode>(cfg));
  rclcpp::shutdown();
  return 0;
}
