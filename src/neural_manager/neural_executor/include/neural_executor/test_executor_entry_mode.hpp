/****************************************************************************
 * Copyright (c) 2025 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/
/**
 * @file test_executor_entry_mode.hpp
 * @brief Mode to activate execution of test neural manual control entry
 * @author steven cheng
 * @date created on 2025.03.20
 */

#pragma once

#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/experimental/trajectory.hpp>
#include <rclcpp/rclcpp.hpp>

class TestExecutorEntryMode : public px4_ros2::ModeBase
{
public:
  explicit TestExecutorEntryMode(rclcpp::Node & node)
  : ModeBase(node, Settings{"Test Neural Executor"}.activateEvenWhileDisarmed(true))
  {
    _trajectory_setpoint = std::make_shared<px4_ros2::TrajectorySetpointType>(*this);
  }

  ~TestExecutorEntryMode() override = default;

protected:
  void updateSetpoint(float dt_s) override
  {
  }

  void onActivate() override
  {
    RCLCPP_INFO(node().get_logger(), "TestExecutorEntryMode activated");
  }

  void onDeactivate() override
  {
    RCLCPP_INFO(node().get_logger(), "TestExecutorEntryMode deactivated");
  }

private:
  std::shared_ptr<px4_ros2::TrajectorySetpointType> _trajectory_setpoint;
};
