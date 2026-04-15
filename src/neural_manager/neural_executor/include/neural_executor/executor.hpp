#pragma once

#include <neural_executor/mavlink_logger.hpp>
#include <px4_msgs/msg/trajectory_setpoint.hpp>
#include <px4_msgs/msg/vehicle_acc_rates_setpoint.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <px4_ros2/common/context.hpp>
#include <px4_ros2/components/manual_control_input.hpp>
#include <px4_ros2/components/mode_executor.hpp>
#include <px4_ros2/odometry/local_position.hpp>
#include <px4_ros2/vehicle_state/vehicle_status.hpp>

#include <Eigen/Core>
#include <chrono>

using namespace std::chrono_literals;

class NeuralExecutor : public px4_ros2::ModeExecutorBase {
  static constexpr uint16_t RC_ARM_DISARM_MASK = 512;
  static constexpr uint16_t RC_NN_CMD_MASK = 1024;
  static constexpr uint8_t POSCTL_NAV_STATE =
      px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_POSCTL;
  static constexpr double NEURAL_CONTROL_TIMEOUT_S = 0.5;

public:
  enum class State {
    TakingOff,
    Position,
    NeuralCtrl,
  };

  NeuralExecutor(px4_ros2::ModeBase &owned_mode,
                 px4_ros2::ModeBase &neural_mode)
      : ModeExecutorBase(Settings{Settings::Activation::ActivateOnlyWhenArmed},
                         owned_mode),
        _neural_mode(neural_mode),
        _context(std::make_unique<px4_ros2::Context>(node())),
        _vehicle_status(std::make_unique<px4_ros2::VehicleStatus>(*_context)),
        _manual_control_input(
            std::make_unique<px4_ros2::ManualControlInput>(*_context, false)) {
    RCLCPP_INFO(
        node().get_logger(),
        "VehicleStatus and ManualControlInput are required dependencies");
    _rc_poll_timer =
        node().create_wall_timer(50ms, [this]() { handleRCInput(); });

    _neural_control_sub =
        node().create_subscription<px4_msgs::msg::VehicleAccRatesSetpoint>(
            "/neural/control", rclcpp::SensorDataQoS(),
            [this](const px4_msgs::msg::VehicleAccRatesSetpoint::SharedPtr) {
              _neural_control_received = true;
              _last_neural_control_time = node().get_clock()->now();
            });

    _mavlink_logger = std::make_unique<neural_executor::MavlinkLogger>(node());

    _odometry_position =
        std::make_unique<px4_ros2::OdometryLocalPosition>(*_context);
    _target_pub = node().create_publisher<px4_msgs::msg::TrajectorySetpoint>(
        "/neural/target", 10);

    // Declare and read target offset parameter
    node().declare_parameter("target_offset",
                             std::vector<double>{0.0, 0.0, 0.0});
    auto offset_param = node().get_parameter("target_offset").as_double_array();
    if (offset_param.size() == 3) {
      _target_offset =
          Eigen::Vector3d(offset_param[0], offset_param[1], offset_param[2]);
    } else {
      RCLCPP_WARN(node().get_logger(),
                  "target_offset must have 3 elements, using default (0,0,0)");
      _target_offset = Eigen::Vector3d::Zero();
    }
  }

  void onActivate() override {
    RCLCPP_INFO(node().get_logger(), "NeuralExecutor: Starting mission");
    _mavlink_logger->info("[Neural] Executor activated");
    runState(State::TakingOff, px4_ros2::Result::Success);
  }

  void onDeactivate(DeactivateReason reason) override {
    RCLCPP_WARN(node().get_logger(), "NeuralExecutor: Deactivated");
    _mavlink_logger->warning("[Neural] Executor deactivated");
    stopTargetPublishing();
  }

  void runState(State state, px4_ros2::Result previous_result) {
    if (previous_result != px4_ros2::Result::Success) {
      RCLCPP_ERROR(node().get_logger(), "State failed: %s",
                   resultToString(previous_result));

      if (state == State::TakingOff) {
        RCLCPP_WARN(node().get_logger(),
                    "Takeoff failed, switching to Position mode to wait for RC "
                    "trigger");
        _mavlink_logger->error("[Neural] Takeoff failed");
      }

      RCLCPP_WARN(node().get_logger(),
                  "State operation failed, falling back to Position mode");
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
      if (!_vehicle_status->lastValid()) {
        RCLCPP_INFO(node().get_logger(),
                    "State: Position - waiting for vehicle status");
        _mavlink_logger->notice("[Neural] Waiting for vehicle status");
        break;
      }

      startTargetPublishing();

      if (_vehicle_status->navState() != POSCTL_NAV_STATE) {
        RCLCPP_INFO(node().get_logger(),
                    "State: Position - switching to Position mode");
        _mavlink_logger->info("[Neural] Switching to Position mode");
        scheduleMode(px4_ros2::ModeBase::kModeIDPosctl,
                     [this](px4_ros2::Result pos_result) {
                       handlePositionSwitchResult(pos_result);
                     });
      } else {
        RCLCPP_INFO(node().get_logger(),
                    "State: Position - waiting for RC trigger");
        _mavlink_logger->notice("[Neural] Ready - waiting RC trigger");
      }
      break;

    case State::NeuralCtrl:
      RCLCPP_INFO(node().get_logger(), "State: NeuralCtrl");
      _mavlink_logger->info("[Neural] Entering NeuralCtrl mode");
      stopTargetPublishing();
      scheduleMode(_neural_mode.id(), [this](px4_ros2::Result result) {
        if (result == px4_ros2::Result::Success) {
          RCLCPP_INFO(node().get_logger(),
                      "NeuralCtrl succeeded - continuing in NeuralCtrl mode");
          _mavlink_logger->info("[Neural] NeuralCtrl completed");
        } else {
          RCLCPP_WARN(node().get_logger(),
                      "NeuralCtrl failed/interrupted, returning to Position");
          _mavlink_logger->warning("[Neural] NeuralCtrl interrupted");
          runState(State::Position, px4_ros2::Result::ModeFailureOther);
        }
      });
      break;
    }
  }

private:
  px4_ros2::ModeBase &_neural_mode;

  std::unique_ptr<px4_ros2::Context> _context;
  std::unique_ptr<px4_ros2::VehicleStatus> _vehicle_status;
  std::unique_ptr<px4_ros2::ManualControlInput> _manual_control_input;

  rclcpp::TimerBase::SharedPtr _rc_poll_timer;
  bool _aux1_high_last{false};
  bool _aux1_low_last{false};
  bool _button_pressed_last{false};
  bool _arm_disarm_pressed_last{false};

  rclcpp::Subscription<px4_msgs::msg::VehicleAccRatesSetpoint>::SharedPtr
      _neural_control_sub;
  bool _neural_control_received{false};
  rclcpp::Time _last_neural_control_time;

  std::unique_ptr<neural_executor::MavlinkLogger> _mavlink_logger;

  std::unique_ptr<px4_ros2::OdometryLocalPosition> _odometry_position;
  rclcpp::Publisher<px4_msgs::msg::TrajectorySetpoint>::SharedPtr _target_pub;
  rclcpp::TimerBase::SharedPtr _target_publish_timer;

  Eigen::Vector3d _target_offset{0.0, 0.0, 0.0};

  bool isNeuralControlAvailable() {
    if (!_neural_control_received)
      return false;
    auto elapsed =
        (node().get_clock()->now() - _last_neural_control_time).seconds();
    return elapsed < NEURAL_CONTROL_TIMEOUT_S;
  }

  void handleRCInput() {
    if (!_vehicle_status->lastValid())
      return;
    if (!_manual_control_input->isValid())
      return;

    bool arm_disarm_pressed =
        _manual_control_input->buttons() == RC_ARM_DISARM_MASK;
    bool arm_disarm_rising = arm_disarm_pressed && !_arm_disarm_pressed_last;

    // In simulation, we use button to trigger arm or disarm
    if (arm_disarm_rising) {
      if (isArmed()) {
        RCLCPP_INFO(node().get_logger(), "Disarming via button=512");
        _mavlink_logger->info("[Neural] Disarming via button");
        disarm([this](px4_ros2::Result result) {
          if (result != px4_ros2::Result::Success) {
            RCLCPP_ERROR(node().get_logger(), "Disarm failed: %s",
                         resultToString(result));
            _mavlink_logger->error("[Neural] Disarm failed");
          }
        });
      } else {
        RCLCPP_INFO(node().get_logger(), "Arming via button=512");
        _mavlink_logger->info("[Neural] Arming via button");
        arm([this](px4_ros2::Result result) {
          if (result != px4_ros2::Result::Success) {
            RCLCPP_ERROR(node().get_logger(), "Arm failed: %s",
                         resultToString(result));
            _mavlink_logger->error("[Neural] Arm failed");
          }
        });
      }
    }
    _arm_disarm_pressed_last = arm_disarm_pressed;

    // In realworld, we must be sure in position mode to trigger neural control
    if (_vehicle_status->navState() != POSCTL_NAV_STATE)
      return;

    bool aux1_high = _manual_control_input->aux1() > 0.5f;
    bool aux1_low = _manual_control_input->aux1() < -0.5f;
    bool button_pressed = _manual_control_input->buttons() == RC_NN_CMD_MASK;

    bool aux1_rising = aux1_high && !_aux1_high_last;
    bool aux1_falling = aux1_low && !_aux1_low_last;
    bool button_rising = button_pressed && !_button_pressed_last;

    if (aux1_rising || aux1_falling || button_rising) {
      if (!isNeuralControlAvailable()) {
        RCLCPP_WARN(node().get_logger(),
                    "Neural control not available, trigger ignored");
        _mavlink_logger->warning("[Neural] neural_infer not responding");
      } else {
        RCLCPP_INFO(node().get_logger(),
                    "Neural control available, entering NeuralCtrl");
        _mavlink_logger->info("[Neural] Entering NeuralCtrl mode");
        runState(State::NeuralCtrl, px4_ros2::Result::Success);
      }
    }

    _aux1_high_last = aux1_high;
    _aux1_low_last = aux1_low;
    _button_pressed_last = button_pressed;
  }

  void publishCurrentPositionAsTarget() {
    if (!_odometry_position->positionXYValid() ||
        !_odometry_position->positionZValid()) {
      RCLCPP_WARN_THROTTLE(node().get_logger(), *node().get_clock(), 2000,
                           "Position not valid, cannot publish target");
      return;
    }

    auto pos = _odometry_position->positionNed();
    px4_msgs::msg::TrajectorySetpoint msg;
    msg.timestamp = node().get_clock()->now().nanoseconds() / 1000;
    msg.position[0] = pos.x() + _target_offset.x();
    msg.position[1] = pos.y() + _target_offset.y();
    msg.position[2] = pos.z() + _target_offset.z();
    msg.velocity[0] = NAN;
    msg.velocity[1] = NAN;
    msg.velocity[2] = NAN;
    msg.acceleration[0] = NAN;
    msg.acceleration[1] = NAN;
    msg.acceleration[2] = NAN;

    _target_pub->publish(msg);
  }

  void startTargetPublishing() {
    if (_target_publish_timer)
      return;

    _target_publish_timer =
        node().create_wall_timer(std::chrono::milliseconds(20), [this]() {
          publishCurrentPositionAsTarget();
        });

    RCLCPP_INFO(node().get_logger(),
                "Started publishing target position at 50Hz");
  }

  void stopTargetPublishing() {
    if (_target_publish_timer) {
      _target_publish_timer->cancel();
      _target_publish_timer = nullptr;
    }
  }

  void handlePositionSwitchResult(px4_ros2::Result result) {
    if (result == px4_ros2::Result::Success)
      return;

    switch (result) {
    case px4_ros2::Result::Rejected:
      RCLCPP_ERROR(node().get_logger(),
                   "Failed to switch to Position mode: Rejected");
      _mavlink_logger->error("[Neural] Position mode rejected");
      break;
    case px4_ros2::Result::Timeout:
      RCLCPP_ERROR(node().get_logger(),
                   "Failed to switch to Position mode: Timeout");
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
      RCLCPP_ERROR(node().get_logger(), "Schedule position mode failed: %s",
                   resultToString(result));
      _mavlink_logger->error("[Neural] Position mode failed");
      break;
    }
  }
};
