/****************************************************************************
 * Copyright (c) 2025 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/
/**
 * @file test_executor.hpp
 * @brief Test executor using TestNeuralManualMode instead of NeuralCtrlMode
 * @author steven cheng
 * @date created on 2025.03.20
 */

#pragma once

#include <px4_ros2/components/mode_executor.hpp>
#include <px4_ros2/common/context.hpp>
#include <px4_ros2/vehicle_state/vehicle_status.hpp>
#include <px4_ros2/components/manual_control_input.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <neural_executor/mavlink_logger.hpp>

using namespace std::chrono_literals;

class TestExecutor : public px4_ros2::ModeExecutorBase
{
  static constexpr uint16_t RC_ARM_DISARM_MASK = 512;
  static constexpr uint16_t RC_NN_CMD_MASK = 1024;
  static constexpr uint8_t POSCTL_NAV_STATE = px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_POSCTL;
public:
  enum class State
  {
    TakingOff,
    Position,
    NeuralManual,
  };

  TestExecutor(px4_ros2::ModeBase & owned_mode, px4_ros2::ModeBase & neural_manual_mode)
  : ModeExecutorBase(
      Settings{Settings::Activation::ActivateOnlyWhenArmed},
      owned_mode),
    _neural_manual_mode(neural_manual_mode),
    _context(std::make_unique<px4_ros2::Context>(node())),
    _vehicle_status(std::make_unique<px4_ros2::VehicleStatus>(*_context)),
    _manual_control_input(std::make_unique<px4_ros2::ManualControlInput>(*_context, false))
  {
    RCLCPP_INFO(node().get_logger(), "VehicleStatus and ManualControlInput are required dependencies");
    _rc_poll_timer = node().create_wall_timer(50ms, [this]() { handleRCInput(); });
    _mavlink_logger = std::make_unique<neural_executor::MavlinkLogger>(node());
  }

  void onActivate() override
  {
    RCLCPP_INFO(node().get_logger(), "TestExecutor: Starting mission");
    _mavlink_logger->info("[Test] Executor activated");
    runState(State::TakingOff, px4_ros2::Result::Success);
  }

  void onDeactivate(DeactivateReason reason) override
  {
    RCLCPP_WARN(node().get_logger(), "TestExecutor: Deactivated");
    _mavlink_logger->warning("[Test] Executor deactivated");
  }

  void runState(State state, px4_ros2::Result previous_result)
  {
    if (previous_result != px4_ros2::Result::Success) {
      RCLCPP_ERROR(node().get_logger(), "State failed: %s", resultToString(previous_result));

      if (state == State::TakingOff) {
        RCLCPP_WARN(node().get_logger(), "Takeoff failed, switching to Position mode to wait for RC trigger");
        _mavlink_logger->error("[Test] Takeoff failed");
      }

      RCLCPP_WARN(node().get_logger(), "State operation failed, falling back to Position mode");
      _mavlink_logger->warning("[Test] Falling back to Position mode");
      runState(State::Position, px4_ros2::Result::Success);
      return;
    }

    switch (state) {
      case State::TakingOff:
        RCLCPP_INFO(node().get_logger(), "State: TakingOff");
        _mavlink_logger->info("[Test] Taking off");
        takeoff([this](px4_ros2::Result result) {
          runState(State::Position, result);
        });
        break;

      case State::Position:
        if (!_vehicle_status->lastValid()) {
          RCLCPP_INFO(node().get_logger(), "State: Position - waiting for vehicle status");
          _mavlink_logger->notice("[Test] Waiting for vehicle status");
          break;
        }

        if (_vehicle_status->navState() != POSCTL_NAV_STATE) {
          RCLCPP_INFO(node().get_logger(), "State: Position - switching to Position mode");
          _mavlink_logger->info("[Test] Switching to Position mode");
          scheduleMode(px4_ros2::ModeBase::kModeIDPosctl, [this](px4_ros2::Result pos_result) {
            handlePositionSwitchResult(pos_result);
          });
        }
        RCLCPP_INFO(node().get_logger(), "State: Position - waiting for RC trigger");
        _mavlink_logger->notice("[Test] Ready - waiting RC trigger");
        break;

      case State::NeuralManual:
        RCLCPP_INFO(node().get_logger(), "State: NeuralManual");
        _mavlink_logger->info("[Test] Entering NeuralManual mode");
        scheduleMode(_neural_manual_mode.id(), [this](px4_ros2::Result result) {
          if (result == px4_ros2::Result::Success) {
            RCLCPP_INFO(node().get_logger(), "NeuralManual succeeded - continuing in NeuralManual mode");
            _mavlink_logger->info("[Test] NeuralManual completed");
          } else {
            RCLCPP_WARN(node().get_logger(), "NeuralManual failed/interrupted, returning to Position");
            _mavlink_logger->warning("[Test] NeuralManual interrupted");
            runState(State::Position, px4_ros2::Result::ModeFailureOther);
          }
        });
        break;

    }
  }

private:
  px4_ros2::ModeBase & _neural_manual_mode;

  std::unique_ptr<px4_ros2::Context> _context;
  std::unique_ptr<px4_ros2::VehicleStatus> _vehicle_status;
  std::unique_ptr<px4_ros2::ManualControlInput> _manual_control_input;

  rclcpp::TimerBase::SharedPtr _rc_poll_timer;
  bool _button_pressed_last{false};
  bool _arm_disarm_pressed_last{false};

  std::unique_ptr<neural_executor::MavlinkLogger> _mavlink_logger;

  void handleRCInput()
  {
    if (!_vehicle_status->lastValid()) return;
    if (!_manual_control_input->isValid()) return;

    bool arm_disarm_pressed = _manual_control_input->buttons() == RC_ARM_DISARM_MASK;
    bool arm_disarm_rising = arm_disarm_pressed && !_arm_disarm_pressed_last;

    if (arm_disarm_rising) {
      if (isArmed()) {
        RCLCPP_INFO(node().get_logger(), "Disarming via button=512");
        _mavlink_logger->info("[Test] Disarming via button");
        disarm([this](px4_ros2::Result result) {
          if (result != px4_ros2::Result::Success) {
            RCLCPP_ERROR(node().get_logger(), "Disarm failed: %s", resultToString(result));
            _mavlink_logger->error("[Test] Disarm failed");
          }
        });
      } else {
        RCLCPP_INFO(node().get_logger(), "Arming via button=512");
        _mavlink_logger->info("[Test] Arming via button");
        arm([this](px4_ros2::Result result) {
          if (result != px4_ros2::Result::Success) {
            RCLCPP_ERROR(node().get_logger(), "Arm failed: %s", resultToString(result));
            _mavlink_logger->error("[Test] Arm failed");
          }
        });
      }
    }
    _arm_disarm_pressed_last = arm_disarm_pressed;

    if (_vehicle_status->navState() != POSCTL_NAV_STATE) return;

    bool button_pressed = _manual_control_input->buttons() == RC_NN_CMD_MASK;

    bool button_rising = button_pressed && !_button_pressed_last;

    if (button_rising) {
      runState(State::NeuralManual, px4_ros2::Result::Success);
    }

    _button_pressed_last = button_pressed;
  }

  void handlePositionSwitchResult(px4_ros2::Result result)
  {
    if (result == px4_ros2::Result::Success) return;

    if (result == px4_ros2::Result::Deactivated) {
      RCLCPP_WARN(node().get_logger(), "Position mode request deactivated");
      _mavlink_logger->warning("[Test] Position mode deactivated");
      return;
    }

    RCLCPP_ERROR(
      node().get_logger(), "Failed to switch to Position mode: %s",
      resultToString(result));
    _mavlink_logger->error("[Test] Position mode switch failed");
  }
};
