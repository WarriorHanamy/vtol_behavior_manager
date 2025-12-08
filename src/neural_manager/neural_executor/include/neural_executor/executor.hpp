#pragma once

#include <px4_ros2/components/mode_executor.hpp>
#include <px4_msgs/msg/manual_control_setpoint.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>
#include <px4_msgs/msg/vehicle_local_position.hpp>
#include <px4_ros2/utils/message_version.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <yaml-cpp/yaml.h>
#include <Eigen/Dense>

using namespace std::chrono_literals; // NOLINT

class NeuralExecutor : public px4_ros2::ModeExecutorBase
{
static constexpr uint16_t RC_NN_CMD_MASK = 1024;
static constexpr uint8_t POSCTL_NAV_STATE = px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_POSCTL;

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


  struct Config
  {
    float position_timeout = 1.0f;
    float rc_timeout = 0.5f;
    float target_tolerance = 0.5f;
    float still_wait_time = 5.0f;
    float max_velocity = 2.0f;
    std::vector<Eigen::Vector3f> waypoints;
  };

  NeuralExecutor(
    px4_ros2::ModeBase & owned_mode,
    px4_ros2::ModeBase & neural_mode)
  : ModeExecutorBase(
      px4_ros2::ModeExecutorBase::Settings{
        px4_ros2::ModeExecutorBase::Settings::Activation::ActivateOnlyWhenArmed
      },
      owned_mode),
    _neural_mode(neural_mode)
  {
    setupRCInput();
    loadConfig();
  }

  void onActivate() override
  {
    RCLCPP_INFO(node().get_logger(), "NeuralExecutor: Starting mission");
    _current_nav_state = 0;
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

      // If takeoff failed, fallback to Position mode and wait for RC trigger
      if (state == State::TakingOff) {
        RCLCPP_WARN(node().get_logger(), "Takeoff failed, switching to Position mode to wait for RC trigger");
        runState(State::Position, px4_ros2::Result::Success);
        return;
      }

      // For other state failures, also fallback to Position mode
      RCLCPP_WARN(node().get_logger(), "State operation failed, falling back to Position mode");
      runState(State::Position, px4_ros2::Result::Success);
      return;
    }

    switch (state) {
      case State::TakingOff:
        RCLCPP_INFO(node().get_logger(), "State: TakingOff");
        takeoff([this](px4_ros2::Result result) {
          runState(State::Position, result); // run this function ,when complete signal received.
        });
        break;

      case State::Position:
        if(_current_nav_state != POSCTL_NAV_STATE) {
          RCLCPP_INFO(node().get_logger(), "State: Position - switching to Position mode");
          scheduleMode(px4_ros2::ModeBase::kModeIDPosctl, [this](px4_ros2::Result pos_result) {
            handlePositionSwitchResult(pos_result);
          });
        }
        RCLCPP_INFO(node().get_logger(), "State: Position - waiting for RC trigger");
        break;

      case State::NeuralCtrl:
        RCLCPP_INFO(node().get_logger(), "State: NeuralCtrl");
        scheduleMode(
          _neural_mode.id(), [this](px4_ros2::Result result) {
            if (result == px4_ros2::Result::Success) {
              RCLCPP_INFO(node().get_logger(), "NeuralCtrl succeeded - target reached, returning to Position mode to stop");
              scheduleMode(px4_ros2::ModeBase::kModeIDPosctl, [this](px4_ros2::Result pos_result) {
                handlePositionSwitchResult(pos_result);
              });
              runState(State::WaitingStill, px4_ros2::Result::Success);
            } else {
              RCLCPP_WARN(node().get_logger(), "NeuralCtrl failed/interrupted, returning to Position");
              runState(State::Position, px4_ros2::Result::Success);
            }
          });
        break;

      case State::WaitingStill:
        RCLCPP_INFO(node().get_logger(), "State: WaitingStill - checking for stillness before landing");
        // Initialize the start time for waiting
        _still_wait_start_time = node().get_clock()->now();
        // Check if vehicle has been still for the minimum wait time
        _still_check_timer = node().create_wall_timer(
          std::chrono::milliseconds(500),
          [this]() {
            const auto current_time = node().get_clock()->now();
            const auto elapsed_seconds = (current_time - _still_wait_start_time).seconds();

            // Check if vehicle is still and target time has been reached
            if ( isVehicleStill() && (elapsed_seconds >= _config.still_wait_time) ) {
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
        waitUntilDisarmed([this](px4_ros2::Result result) {
          RCLCPP_INFO(node().get_logger(), "Mission complete");
        });
        break;
    }
}

private:
  // Core components
  px4_ros2::ModeBase & _neural_mode;
  Config _config;

  // RC trigger monitoring
  rclcpp::Subscription<px4_msgs::msg::ManualControlSetpoint>::SharedPtr _rc_sub;
  rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr _vehicle_status_sub;
  rclcpp::Subscription<px4_msgs::msg::VehicleLocalPosition>::SharedPtr _vehicle_position_sub;
  uint8_t _current_nav_state;

  Eigen::Vector3f _current_velocity;

  // Timers
  rclcpp::TimerBase::SharedPtr _retry_timer;
  rclcpp::TimerBase::SharedPtr _still_check_timer;
  rclcpp::Time _still_wait_start_time;


  // Setup functions
  void setupRCInput()
  {
    _vehicle_status_sub = node().create_subscription<px4_msgs::msg::VehicleStatus>(
      "/fmu/out/vehicle_status" + px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleStatus>(),
      rclcpp::SensorDataQoS(),
      [this](const px4_msgs::msg::VehicleStatus::SharedPtr msg) {
        _current_nav_state = msg->nav_state;
      });

    _vehicle_position_sub = node().create_subscription<px4_msgs::msg::VehicleLocalPosition>(
      "/fmu/out/vehicle_local_position" + px4_ros2::getMessageNameVersion<px4_msgs::msg::VehicleLocalPosition>(),
      rclcpp::SensorDataQoS(),
      [this](const px4_msgs::msg::VehicleLocalPosition::SharedPtr msg) {
          _current_velocity = Eigen::Vector3f(msg->vx, msg->vy, msg->vz);
      });

    _rc_sub = node().create_subscription<px4_msgs::msg::ManualControlSetpoint>(
      "/fmu/out/manual_control_setpoint" + px4_ros2::getMessageNameVersion<px4_msgs::msg::ManualControlSetpoint>(),
      rclcpp::SensorDataQoS(),
      [this](const px4_msgs::msg::ManualControlSetpoint::SharedPtr msg) {
        handleRCInput(msg);
      });
  }


  void handleRCInput(const px4_msgs::msg::ManualControlSetpoint::SharedPtr msg)
  {
    // Only process if in Position mode
    static bool button_pressed_last = false;

    if (_current_nav_state != POSCTL_NAV_STATE) {
      return;
    }

    bool button_pressed_now = (msg->buttons == RC_NN_CMD_MASK);

    if (button_pressed_now && !button_pressed_last) {
      // Rising edge detected - trigger Neural!
      runState(State::NeuralCtrl, px4_ros2::Result::Success);
    }

    button_pressed_last = button_pressed_now;  
  }

  void handlePositionSwitchResult(px4_ros2::Result result)
  {
    if (result != px4_ros2::Result::Success) {
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
  }

  // Utility functions
  bool isVehicleStill() const
  {
    const float velocity_magnitude = _current_velocity.norm();
    return velocity_magnitude < 0.2f; // 0.2 m/s threshold for "still"
  }

  // REC: please making config process more accessible, it's too lengthy.
  void loadConfig()
  {
    // Try to load config file from parameter first
    std::string config_file;
    if (node().get_parameter("config_file", config_file) && !config_file.empty()) {
      loadConfigFromFile(config_file);
    } else {
      RCLCPP_WARN(node().get_logger(), "No config_file parameter found, using default values");
    }

    // Override with ROS parameters if they exist (allow runtime override)
    node().declare_parameter("position_timeout", _config.position_timeout);
    node().declare_parameter("rc_timeout", _config.rc_timeout);
    node().declare_parameter("target_tolerance", _config.target_tolerance);
    node().declare_parameter("still_wait_time", _config.still_wait_time);
    node().declare_parameter("max_velocity", _config.max_velocity);

    // Load ROS parameters (override YAML values if set)
    double param_value = node().get_parameter("position_timeout").as_double();
    if (param_value != _config.position_timeout) {
      RCLCPP_INFO(node().get_logger(), "Overriding position_timeout: %.1f -> %.1f", _config.position_timeout, param_value);
      _config.position_timeout = param_value;
    }

    param_value = node().get_parameter("rc_timeout").as_double();
    if (param_value != _config.rc_timeout) {
      RCLCPP_INFO(node().get_logger(), "Overriding rc_timeout: %.1f -> %.1f", _config.rc_timeout, param_value);
      _config.rc_timeout = param_value;
    }

    param_value = node().get_parameter("target_tolerance").as_double();
    if (param_value != _config.target_tolerance) {
      RCLCPP_INFO(node().get_logger(), "Overriding target_tolerance: %.1f -> %.1f", _config.target_tolerance, param_value);
      _config.target_tolerance = param_value;
    }

    param_value = node().get_parameter("still_wait_time").as_double();
    if (param_value != _config.still_wait_time) {
      RCLCPP_INFO(node().get_logger(), "Overriding still_wait_time: %.1f -> %.1f", _config.still_wait_time, param_value);
      _config.still_wait_time = param_value;
    }

    param_value = node().get_parameter("max_velocity").as_double();
    if (param_value != _config.max_velocity) {
      RCLCPP_INFO(node().get_logger(), "Overriding max_velocity: %.1f -> %.1f", _config.max_velocity, param_value);
      _config.max_velocity = param_value;
    }

    RCLCPP_INFO(node().get_logger(), "Final configuration: pos_timeout=%.1f, rc_timeout=%.1f, tolerance=%.1f, still_wait=%.1f, max_vel=%.1f",
                _config.position_timeout, _config.rc_timeout, _config.target_tolerance, _config.still_wait_time, _config.max_velocity);
  }

  void loadConfigFromFile(const std::string& config_file)
  {
    try {
      YAML::Node config = YAML::LoadFile(config_file);

      if (config["failsafe_config"]) {
        auto failsafe = config["failsafe_config"];

        if (failsafe["position_timeout"]) {
          _config.position_timeout = failsafe["position_timeout"].as<float>();
        }
        if (failsafe["rc_timeout"]) {
          _config.rc_timeout = failsafe["rc_timeout"].as<float>();
        }
        if (failsafe["target_tolerance"]) {
          _config.target_tolerance = failsafe["target_tolerance"].as<float>();
        }
        if (failsafe["still_wait_time"]) {
          _config.still_wait_time = failsafe["still_wait_time"].as<float>();
        }
        if (failsafe["max_velocity"]) {
          _config.max_velocity = failsafe["max_velocity"].as<float>();
        }

        RCLCPP_INFO(node().get_logger(), "Loaded configuration from YAML: %s", config_file.c_str());
      } else {
        RCLCPP_WARN(node().get_logger(), "No failsafe_config section found in YAML file");
      }

    } catch (const YAML::Exception& e) {
      RCLCPP_ERROR(node().get_logger(), "Failed to load config file '%s': %s", config_file.c_str(), e.what());
    }
  }
};