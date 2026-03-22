#pragma once

#include <px4_ros2/components/mode_executor.hpp>
#include <px4_ros2/common/context.hpp>
#include <px4_ros2/vehicle_state/vehicle_status.hpp>
#include <px4_ros2/components/manual_control_input.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>

using namespace std::chrono_literals;

class NeuralExecutor : public px4_ros2::ModeExecutorBase
{
  static constexpr uint16_t RC_NN_CMD_MASK = 1024;
  static constexpr uint8_t POSCTL_NAV_STATE = px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_POSCTL;
  static constexpr double STILL_WAIT_TIME_S = 3.0;

public:
  enum class State
  {
    TakingOff,
    Position,
    NeuralCtrl,
    WaitingStill,
    Land,
    WaitUntilDisarmed,
  };

  NeuralExecutor(px4_ros2::ModeBase & owned_mode, px4_ros2::ModeBase & neural_mode)
  : ModeExecutorBase(
      Settings{Settings::Activation::ActivateOnlyWhenArmed},
      owned_mode),
    _neural_mode(neural_mode),
    _context(std::make_unique<px4_ros2::Context>(node())),
    _vehicle_status(std::make_unique<px4_ros2::VehicleStatus>(*_context)),
    _manual_control_input(std::make_unique<px4_ros2::ManualControlInput>(*_context, true))
  {
    _rc_poll_timer = node().create_wall_timer(50ms, [this]() { handleRCInput(); });
  }

  void onActivate() override
  {
    RCLCPP_INFO(node().get_logger(), "NeuralExecutor: Starting mission");
    runState(State::TakingOff, px4_ros2::Result::Success);
  }

  void onDeactivate(DeactivateReason reason) override
  {
    RCLCPP_WARN(node().get_logger(), "NeuralExecutor: Deactivated");
  }

  void runState(State state, px4_ros2::Result previous_result)
  {
    if (previous_result != px4_ros2::Result::Success) {
      RCLCPP_ERROR(node().get_logger(), "State failed: %s", resultToString(previous_result));

      if (state == State::TakingOff) {
        RCLCPP_WARN(node().get_logger(), "Takeoff failed, switching to Position mode to wait for RC trigger");
      }

      RCLCPP_WARN(node().get_logger(), "State operation failed, falling back to Position mode");
      runState(State::Position, px4_ros2::Result::Success);
      return;
    }

    switch (state) {
      case State::TakingOff:
        RCLCPP_INFO(node().get_logger(), "State: TakingOff");
        takeoff([this](px4_ros2::Result result) {
          runState(State::Position, result);
        });
        break;

      case State::Position:
        if (_vehicle_status->navState() != POSCTL_NAV_STATE) {
          RCLCPP_INFO(node().get_logger(), "State: Position - switching to Position mode");
          scheduleMode(px4_ros2::ModeBase::kModeIDPosctl, [this](px4_ros2::Result pos_result) {
            handlePositionSwitchResult(pos_result);
          });
        }
        RCLCPP_INFO(node().get_logger(), "State: Position - waiting for RC trigger");
        break;

      case State::NeuralCtrl:
        RCLCPP_INFO(node().get_logger(), "State: NeuralCtrl");
        scheduleMode(_neural_mode.id(), [this](px4_ros2::Result result) {
          if (result == px4_ros2::Result::Success) {
            RCLCPP_INFO(node().get_logger(), "NeuralCtrl succeeded - continuing in NeuralCtrl mode");
          } else {
            RCLCPP_WARN(node().get_logger(), "NeuralCtrl failed/interrupted, returning to Position");
            runState(State::Position, px4_ros2::Result::ModeFailureOther);
          }
        });
        break;

      case State::WaitingStill:
        RCLCPP_INFO(node().get_logger(), "State: WaitingStill - waiting before landing");
        _still_wait_start_time = node().get_clock()->now();
        _still_check_timer = node().create_wall_timer(
          std::chrono::milliseconds(500),
          [this]() {
            const auto current_time = node().get_clock()->now();
            const auto elapsed_seconds = (current_time - _still_wait_start_time).seconds();
            if (elapsed_seconds >= STILL_WAIT_TIME_S) {
              _still_check_timer->cancel();
              land([this](px4_ros2::Result result) {
                runState(State::WaitUntilDisarmed, result);
              });
            }
          });
        break;

      case State::Land:
        RCLCPP_INFO(node().get_logger(), "State: Land");
        land([this](px4_ros2::Result result) {
          runState(State::WaitUntilDisarmed, result);
        });
        break;

      case State::WaitUntilDisarmed:
        RCLCPP_INFO(node().get_logger(), "State: WaitUntilDisarmed");
        waitUntilDisarmed([this](px4_ros2::Result) {
          RCLCPP_INFO(node().get_logger(), "Mission complete");
        });
        break;
    }
  }

private:
  px4_ros2::ModeBase & _neural_mode;

  std::unique_ptr<px4_ros2::Context> _context;
  std::unique_ptr<px4_ros2::VehicleStatus> _vehicle_status;
  std::unique_ptr<px4_ros2::ManualControlInput> _manual_control_input;

  rclcpp::TimerBase::SharedPtr _rc_poll_timer;
  rclcpp::TimerBase::SharedPtr _still_check_timer;
  rclcpp::Time _still_wait_start_time;

  bool _aux1_high_last{false};
  bool _button_pressed_last{false};

  void handleRCInput()
  {
    if (!_vehicle_status->lastValid()) return;
    if (_vehicle_status->navState() != POSCTL_NAV_STATE) return;
    if (!_manual_control_input->isValid()) return;

    bool aux1_high = _manual_control_input->aux1() > 0.5f;
    bool button_pressed = _manual_control_input->buttons() == RC_NN_CMD_MASK;

    bool aux1_rising = aux1_high && !_aux1_high_last;
    bool button_rising = button_pressed && !_button_pressed_last;

    if (aux1_rising || button_rising) {
      runState(State::NeuralCtrl, px4_ros2::Result::Success);
    }

    _aux1_high_last = aux1_high;
    _button_pressed_last = button_pressed;
  }

  void handlePositionSwitchResult(px4_ros2::Result result)
  {
    if (result == px4_ros2::Result::Success) return;

    switch (result) {
      case px4_ros2::Result::Rejected:
        RCLCPP_ERROR(node().get_logger(), "Failed to switch to Position mode: Rejected");
        break;
      case px4_ros2::Result::Timeout:
        RCLCPP_ERROR(node().get_logger(), "Failed to switch to Position mode: Timeout");
        break;
      case px4_ros2::Result::Interrupted:
        RCLCPP_ERROR(node().get_logger(), "Position mode switch interrupted");
        break;
      case px4_ros2::Result::Deactivated:
        RCLCPP_WARN(node().get_logger(), "Position mode is deactivated");
        break;
      default:
        RCLCPP_ERROR(node().get_logger(), "Schedule position mode failed: %s", resultToString(result));
        break;
    }
  }
};
