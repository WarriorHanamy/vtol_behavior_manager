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
   static constexpr uint16_t RC_TRIGGER_NEURAL_CONTROL_BUTTON_MASK = 1024;
   static constexpr float RC_TRIGGER_NEURAL_CONTROL_RISING_EDGE_AUX1_THRESHOLD = 0.5F;
  static constexpr uint8_t POSCTL_NAV_STATE =
      px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_POSCTL;
  static constexpr double NEURAL_CONTROL_TIMEOUT_S = 0.5;
  static constexpr auto FLOW_DRIVE_PERIOD = 50ms;

public:
  NeuralExecutor(px4_ros2::ModeBase &owned_mode,
                 px4_ros2::ModeBase &neural_mode)
      : ModeExecutorBase(
            Settings{}.activate(Settings::Activation::ActivateAlways),
            owned_mode),
        _neural_mode(neural_mode),
        _context(std::make_unique<px4_ros2::Context>(node())),
        _vehicle_status(std::make_unique<px4_ros2::VehicleStatus>(*_context)),
        _manual_control_input(
            std::make_unique<px4_ros2::ManualControlInput>(owned_mode, false)) {
    RCLCPP_INFO(
        node().get_logger(),
        "VehicleStatus and ManualControlInput are required dependencies");
    // This timer is the executor's top-level flow driver. It samples RC input
    // and advances the Position -> Neural -> Position flow.
    _flow_drive_timer = node().create_wall_timer(
        FLOW_DRIVE_PERIOD, [this]() { driveFlightFlow(); });

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
    _mavlink_logger->info("[Neural Executor] Executor activated");
    enterPositionMode();
  }

  void onDeactivate(DeactivateReason reason) override {
    RCLCPP_WARN(node().get_logger(), "NeuralExecutor: Deactivated");
    _mavlink_logger->warning("[Neural Executor] Executor deactivated");
    stopTargetPublishing();
  }

private:
  px4_ros2::ModeBase &_neural_mode;

  std::unique_ptr<px4_ros2::Context> _context;
  std::unique_ptr<px4_ros2::VehicleStatus> _vehicle_status;
  std::unique_ptr<px4_ros2::ManualControlInput> _manual_control_input;

  rclcpp::TimerBase::SharedPtr _flow_drive_timer;
  bool _aux1_trigger_active_last{false};
  bool _neural_control_button_pressed_last{false};

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

  void enterPositionMode() {
    startTargetPublishing();

    if (_vehicle_status->lastValid() &&
        _vehicle_status->navState() == POSCTL_NAV_STATE) {
      RCLCPP_INFO(node().get_logger(),
                  "Position mode active, waiting for triggers");
      _mavlink_logger->notice("[Neural Executor] Position mode active");
      return;
    }

    RCLCPP_INFO(node().get_logger(), "Requesting Position mode");
    _mavlink_logger->info("[Neural Executor] Switching to Position mode");
    scheduleMode(
        px4_ros2::ModeBase::kModeIDPosctl, [this](px4_ros2::Result result) {
          if (result == px4_ros2::Result::Success ||
              result == px4_ros2::Result::Deactivated) {
            return;
          }

          RCLCPP_ERROR(node().get_logger(), "Position mode request failed: %s",
                       resultToString(result));
          _mavlink_logger->error("[Neural Executor] Position mode switch failed");
        });
  }


   void startNeuralCtrl() {
    RCLCPP_INFO(node().get_logger(), "Starting NeuralCtrl from Position mode");
    _mavlink_logger->info("[Neural Executor] Entering NeuralCtrl mode");
    stopTargetPublishing();

    scheduleMode(_neural_mode.id(), [this](px4_ros2::Result result) {
      if (result == px4_ros2::Result::Deactivated) {
        RCLCPP_WARN(node().get_logger(), "NeuralCtrl deactivated");
        _mavlink_logger->warning("[Neural Executor] NeuralCtrl deactivated");
        return;
      }

      if (result == px4_ros2::Result::Success) {
        RCLCPP_INFO(node().get_logger(),
                    "NeuralCtrl completed, returning to Position");
        _mavlink_logger->info("[Neural Executor] NeuralCtrl completed");
      } else {
        RCLCPP_ERROR(node().get_logger(),
                     "NeuralCtrl failed: %s, returning to Position",
                     resultToString(result));
        _mavlink_logger->error("[Neural Executor] NeuralCtrl failed");
      }

      enterPositionMode();
    });
  }

  void driveFlightFlow() {
    if (!_vehicle_status->lastValid())
      return;
    if (!_manual_control_input->isValid())
      return;

    processNeuralTriggerFlowStep();
  }

  void processNeuralTriggerFlowStep() {
    bool aux1_trigger_active =
        _manual_control_input->aux1() >
        RC_TRIGGER_NEURAL_CONTROL_RISING_EDGE_AUX1_THRESHOLD;
    bool neural_control_button_pressed =
        _manual_control_input->buttons() ==
        RC_TRIGGER_NEURAL_CONTROL_BUTTON_MASK;

    if (_vehicle_status->navState() != POSCTL_NAV_STATE) {
      return;
    }

    bool aux1_trigger_rising =
        aux1_trigger_active && !_aux1_trigger_active_last;
    bool neural_control_button_rising =
        neural_control_button_pressed && !_neural_control_button_pressed_last;

    if (aux1_trigger_rising || neural_control_button_rising) {
      if (!isNeuralControlAvailable()) {
        RCLCPP_WARN(node().get_logger(),
                    "Neural control not available, trigger ignored");
        _mavlink_logger->warning("[Neural Executor] neural_infer not responding");
      } else {
        startNeuralCtrl();
      }
    }

    _aux1_trigger_active_last = aux1_trigger_active;
    _neural_control_button_pressed_last = neural_control_button_pressed;
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
};
