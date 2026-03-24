#pragma once

#include <px4_ros2/components/mode_executor.hpp>
#include <px4_ros2/common/context.hpp>
#include <px4_ros2/vehicle_state/vehicle_status.hpp>
#include <px4_ros2/components/manual_control_input.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <px4_msgs/msg/vehicle_acc_rates_setpoint.hpp>
#include <neural_executor/mavlink_logger.hpp>

#include <chrono>

using namespace std::chrono_literals;

class NeuralExecutor : public px4_ros2::ModeExecutorBase
{
  static constexpr uint16_t RC_NN_CMD_MASK = 1024;
  static constexpr uint8_t POSCTL_NAV_STATE = px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_POSCTL;
  static constexpr double STILL_WAIT_TIME_S = 3.0;
  static constexpr double NEURAL_CONTROL_TIMEOUT_S = 0.5;
  static constexpr double NEURAL_CONTROL_WAIT_S = 2.0;

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

    _neural_control_sub = node().create_subscription<px4_msgs::msg::VehicleAccRatesSetpoint>(
        "/neural/control", rclcpp::SensorDataQoS(),
        [this](const px4_msgs::msg::VehicleAccRatesSetpoint::SharedPtr) {
          _neural_control_received = true;
          _last_neural_control_time = node().get_clock()->now();
        });

    _mavlink_logger = std::make_unique<neural_executor::MavlinkLogger>(node());
  }

  void onActivate() override
  {
    RCLCPP_INFO(node().get_logger(), "NeuralExecutor: Starting mission");
    _mavlink_logger->info("[Neural] Executor activated");
    runState(State::TakingOff, px4_ros2::Result::Success);
  }

  void onDeactivate(DeactivateReason reason) override
  {
    RCLCPP_WARN(node().get_logger(), "NeuralExecutor: Deactivated");
    _mavlink_logger->warning("[Neural] Executor deactivated");
  }

  void runState(State state, px4_ros2::Result previous_result)
  {
    if (previous_result != px4_ros2::Result::Success) {
      RCLCPP_ERROR(node().get_logger(), "State failed: %s", resultToString(previous_result));

      if (state == State::TakingOff) {
        RCLCPP_WARN(node().get_logger(), "Takeoff failed, switching to Position mode to wait for RC trigger");
        _mavlink_logger->error("[Neural] Takeoff failed");
      }

      RCLCPP_WARN(node().get_logger(), "State operation failed, falling back to Position mode");
      _mavlink_logger->warning("[Neural] Falling back to Position mode");
      runState(State::Position, px4_ros2::Result::Success);
      return;
    }

    switch (state) {
      case State::TakingOff:
        RCLCPP_INFO(node().get_logger(), "State: TakingOff");
        _mavlink_logger->info("[Neural] Taking off");
        takeoff([this](px4_ros2::Result result) {
          runState(State::Position, result);
        });
        break;

      case State::Position:
        if (_vehicle_status->navState() != POSCTL_NAV_STATE) {
          RCLCPP_INFO(node().get_logger(), "State: Position - switching to Position mode");
          _mavlink_logger->info("[Neural] Switching to Position mode");
          scheduleMode(px4_ros2::ModeBase::kModeIDPosctl, [this](px4_ros2::Result pos_result) {
            handlePositionSwitchResult(pos_result);
          });
        }
        RCLCPP_INFO(node().get_logger(), "State: Position - waiting for RC trigger");
        _mavlink_logger->notice("[Neural] Ready - waiting RC trigger");
        break;

      case State::NeuralCtrl:
        RCLCPP_INFO(node().get_logger(), "State: NeuralCtrl");
        _mavlink_logger->info("[Neural] Entering NeuralCtrl mode");
        scheduleMode(_neural_mode.id(), [this](px4_ros2::Result result) {
          if (result == px4_ros2::Result::Success) {
            RCLCPP_INFO(node().get_logger(), "NeuralCtrl succeeded - continuing in NeuralCtrl mode");
            _mavlink_logger->info("[Neural] NeuralCtrl completed");
          } else {
            RCLCPP_WARN(node().get_logger(), "NeuralCtrl failed/interrupted, returning to Position");
            _mavlink_logger->warning("[Neural] NeuralCtrl interrupted");
            runState(State::Position, px4_ros2::Result::ModeFailureOther);
          }
        });
        break;

      case State::WaitingStill:
        RCLCPP_INFO(node().get_logger(), "State: WaitingStill - waiting before landing");
        _mavlink_logger->info("[Neural] Waiting before landing");
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
        _mavlink_logger->info("[Neural] Landing");
        land([this](px4_ros2::Result result) {
          runState(State::WaitUntilDisarmed, result);
        });
        break;

      case State::WaitUntilDisarmed:
        RCLCPP_INFO(node().get_logger(), "State: WaitUntilDisarmed");
        _mavlink_logger->info("[Neural] Waiting until disarmed");
        waitUntilDisarmed([this](px4_ros2::Result) {
          RCLCPP_INFO(node().get_logger(), "Mission complete");
          _mavlink_logger->info("[Neural] Mission complete");
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

  rclcpp::Subscription<px4_msgs::msg::VehicleAccRatesSetpoint>::SharedPtr _neural_control_sub;
  bool _neural_control_received{false};
  rclcpp::Time _last_neural_control_time;

  std::unique_ptr<neural_executor::MavlinkLogger> _mavlink_logger;

  bool _waiting_for_neural_control{false};
  rclcpp::Time _neural_wait_start_time;

  bool isNeuralControlAvailable()
  {
    if (!_neural_control_received) return false;
    auto elapsed = (node().get_clock()->now() - _last_neural_control_time).seconds();
    return elapsed < NEURAL_CONTROL_TIMEOUT_S;
  }

  void handleRCInput()
  {
    if (!_vehicle_status->lastValid()) return;
    if (_vehicle_status->navState() != POSCTL_NAV_STATE) return;
    if (!_manual_control_input->isValid()) return;

    if (_waiting_for_neural_control) {
      auto elapsed = (node().get_clock()->now() - _neural_wait_start_time).seconds();
      if (isNeuralControlAvailable()) {
        _waiting_for_neural_control = false;
        RCLCPP_INFO(node().get_logger(), "Neural control available, entering NeuralCtrl");
        _mavlink_logger->info("[Neural] Entering NeuralCtrl mode");
        runState(State::NeuralCtrl, px4_ros2::Result::Success);
      } else if (elapsed >= NEURAL_CONTROL_WAIT_S) {
        _waiting_for_neural_control = false;
        RCLCPP_ERROR(node().get_logger(), "Neural control timeout - cannot enter NeuralCtrl");
        _mavlink_logger->error("[Neural] neural_infer not responding");
      }
      return;
    }

    bool aux1_high = _manual_control_input->aux1() > 0.5f;
    bool button_pressed = _manual_control_input->buttons() == RC_NN_CMD_MASK;

    bool aux1_rising = aux1_high && !_aux1_high_last;
    bool button_rising = button_pressed && !_button_pressed_last;

    if (aux1_rising || button_rising) {
      if (!isNeuralControlAvailable()) {
        _waiting_for_neural_control = true;
        _neural_wait_start_time = node().get_clock()->now();
        RCLCPP_WARN(node().get_logger(), "Neural control not available, waiting...");
        _mavlink_logger->warning("[Neural] Waiting for neural_infer...");
        _aux1_high_last = aux1_high;
        _button_pressed_last = button_pressed;
        return;
      }

      RCLCPP_INFO(node().get_logger(), "Neural control available, entering NeuralCtrl");
      _mavlink_logger->info("[Neural] Entering NeuralCtrl mode");
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
        _mavlink_logger->error("[Neural] Position mode rejected");
        break;
      case px4_ros2::Result::Timeout:
        RCLCPP_ERROR(node().get_logger(), "Failed to switch to Position mode: Timeout");
        _mavlink_logger->error("[Neural] Position mode timeout");
        break;
      case px4_ros2::Result::Interrupted:
        RCLCPP_ERROR(node().get_logger(), "Position mode switch interrupted");
        _mavlink_logger->error("[Neural] Position mode interrupted");
        break;
      case px4_ros2::Result::Deactivated:
        RCLCPP_WARN(node().get_logger(), "Position mode is deactivated");
        _mavlink_logger->warning("[Neural] Position mode deactivated");
        break;
      default:
        RCLCPP_ERROR(node().get_logger(), "Schedule position mode failed: %s", resultToString(result));
        _mavlink_logger->error("[Neural] Position mode failed");
        break;
    }
  }
};
