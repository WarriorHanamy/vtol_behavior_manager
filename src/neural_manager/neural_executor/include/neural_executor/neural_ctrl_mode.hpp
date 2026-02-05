/****************************************************************************
 * Copyright (c) 2023 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/
#pragma once

#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/experimental/acc_rates.hpp>
#include <px4_ros2/control/setpoint_types/experimental/rates.hpp>
#include <px4_ros2/odometry/local_position.hpp>
#include <px4_msgs/msg/vehicle_thrust_acc_setpoint.hpp>
#include <px4_msgs/msg/vehicle_rates_setpoint.hpp>
#include <std_msgs/msg/bool.hpp>
#include <rclcpp/rclcpp.hpp>
#include <yaml-cpp/yaml.h>
#include <Eigen/Core>

/**
 * @class NeuralCtrlMode
 * @brief High-performance neural network controlled flight mode with configurable setpoint handling
 *
 * Supported control modes:
 * - rates_throttle: RatesSetpoint (throttle + body rates)
 * - rates_acc: AccRatesSetpoint (thrust acceleration + body rates)
 */
class NeuralCtrlMode : public px4_ros2::ModeBase
{
public:
  explicit NeuralCtrlMode(rclcpp::Node &arg_node)
      : ModeBase(arg_node, Settings{"NeuralControl"})
  {
    _activation_time = {0};
    _has_neural_setpoint = false;

    // Load control mode from config file
    loadControlModeFromConfig();

    // Initialize appropriate setpoint type based on control mode
    if (_control_mode == "rates_throttle") {
      _rates_setpoint = std::make_shared<px4_ros2::RatesSetpointType>(*this);
      RCLCPP_INFO(_node.get_logger(), "🎮 Neural控制模式: Throttle + Body Rates (RatesSetpoint)");
    } else {
      _acc_rates_setpoint = std::make_shared<px4_ros2::AccRatesSetpointType>(*this);
      RCLCPP_INFO(_node.get_logger(), "🎮 Neural控制模式: Thrust Acceleration + Body Rates (AccRatesSetpoint)");
    }

    _manual_control_input = std::make_shared<px4_ros2::ManualControlInput>(*this);

    subscribeToNeuralControl();
  }

  ~NeuralCtrlMode() override = default;
  
  // Disable copy, enable move for efficiency
  NeuralCtrlMode(const NeuralCtrlMode&) = delete;
  NeuralCtrlMode& operator=(const NeuralCtrlMode&) = delete;
  NeuralCtrlMode(NeuralCtrlMode&&) noexcept = default;
  NeuralCtrlMode& operator=(NeuralCtrlMode&&) noexcept = default;

protected:
  void onActivate() override
  {
    _activation_time = _node.get_clock()->now().seconds();
    _has_neural_setpoint = false;

  }

  void onDeactivate() override
  {
    _activation_time = 0;
    _has_neural_setpoint = false;
    RCLCPP_INFO(_node.get_logger(), "NeuralCtrlMode deactivated");
  }

  void updateSetpoint(float dt_s) override
  {
    if (_manual_control_input->sticks_moving()) [[unlikely]]
    {
      RCLCPP_WARN(_node.get_logger(), "Neural: RC interruption detected!");
      completed(px4_ros2::Result::ModeFailureOther);
      return;
    }

    processNeuralSetpoint();
  }

private:
  // Control mode configuration
  std::string _control_mode;

  // Hot path data (cache locality optimization)
  px4_msgs::msg::VehicleRatesSetpoint _neural_rates_ctrl;
  px4_msgs::msg::VehicleThrustAccSetpoint _neural_acc_rates_ctrl;
  rclcpp::Time _neural_ctrl_timestamp;

  std::shared_ptr<px4_ros2::ManualControlInput> _manual_control_input;
  std::shared_ptr<px4_ros2::RatesSetpointType> _rates_setpoint;
  std::shared_ptr<px4_ros2::AccRatesSetpointType> _acc_rates_setpoint;
  double _activation_time;
  bool _has_neural_setpoint;

  // ROS2 communication
  rclcpp::Subscription<px4_msgs::msg::VehicleRatesSetpoint>::SharedPtr _neural_rates_ctrl_sub;
  rclcpp::Subscription<px4_msgs::msg::VehicleThrustAccSetpoint>::SharedPtr _neural_acc_rates_ctrl_sub;

  void loadControlModeFromConfig()
  {
    // Default control mode
    _control_mode = "rates_throttle";

    // Try to load from config file
    std::string config_file;
    if (_node.get_parameter("config_file", config_file) && !config_file.empty()) {
      try {
        YAML::Node config = YAML::LoadFile(config_file);
        
        if (config["neural_control"] && config["neural_control"]["control_mode"]) {
          _control_mode = config["neural_control"]["control_mode"].as<std::string>();
          
          // Validate control mode
          if (_control_mode != "rates_throttle" && _control_mode != "rates_acc") {
            RCLCPP_ERROR(_node.get_logger(), 
                         "Invalid control_mode '%s' in config. Must be 'rates_throttle' or 'rates_acc'. Using default 'rates_throttle'.",
                         _control_mode.c_str());
            _control_mode = "rates_throttle";
          } else {
            RCLCPP_INFO(_node.get_logger(), "Loaded control_mode from config: %s", _control_mode.c_str());
          }
        } else {
          RCLCPP_WARN(_node.get_logger(), "No neural_control.control_mode found in config file, using default: rates_throttle");
        }
      } catch (const YAML::Exception& e) {
        RCLCPP_ERROR(_node.get_logger(), "Failed to load config file '%s': %s. Using default control_mode.", 
                     config_file.c_str(), e.what());
      }
    } else {
      RCLCPP_WARN(_node.get_logger(), "No config_file parameter found, using default control_mode: rates_throttle");
    }
  }

  void subscribeToNeuralControl()
  {
    if (_control_mode == "rates_throttle") {
      // Subscribe to VehicleRatesSetpoint
      _neural_rates_ctrl_sub = _node.create_subscription<px4_msgs::msg::VehicleRatesSetpoint>(
          "/neural/control", rclcpp::SensorDataQoS(),
          [this](const px4_msgs::msg::VehicleRatesSetpoint::SharedPtr msg) {
            _neural_rates_ctrl = *msg;
            _neural_ctrl_timestamp = _node.get_clock()->now();
            _has_neural_setpoint = true;
          });
      RCLCPP_INFO(_node.get_logger(), "Neural: Subscribed to /neural/control (VehicleRatesSetpoint)");
    } else {
      // Subscribe to VehicleThrustAccSetpoint
      _neural_acc_rates_ctrl_sub = _node.create_subscription<px4_msgs::msg::VehicleThrustAccSetpoint>(
          "/neural/control", rclcpp::SensorDataQoS(),
          [this](const px4_msgs::msg::VehicleThrustAccSetpoint::SharedPtr msg) {
            _neural_acc_rates_ctrl = *msg;
            _neural_ctrl_timestamp = _node.get_clock()->now();
            _has_neural_setpoint = true;
          });
      RCLCPP_INFO(_node.get_logger(), "Neural: Subscribed to /neural/control (VehicleThrustAccSetpoint)");
    }
  }

  inline void processNeuralSetpoint()
  {
    if (!_has_neural_setpoint) [[unlikely]] {
      RCLCPP_INFO_THROTTLE(_node.get_logger(), *_node.get_clock(), 1000,
                           "Neural: Waiting for setpoint...");
      return;
    }

    RCLCPP_WARN_THROTTLE(_node.get_logger(), *_node.get_clock(), 1000,
                         "Neural: Applying setpoint...");

    if (_control_mode == "rates_throttle") {
      applyRatesSetpoint(_neural_rates_ctrl);
    } else {
      // Zero out yaw rate for acc_rates mode (if needed)
      _neural_acc_rates_ctrl.rates_sp[2] = 0.0f;
      applyAccRatesSetpoint(_neural_acc_rates_ctrl);
    }
  }

  inline void applyRatesSetpoint(const px4_msgs::msg::VehicleRatesSetpoint& setpoint)
  {
    const Eigen::Vector3f rates_sp{
      setpoint.roll,
      setpoint.pitch,
      setpoint.yaw};
    const Eigen::Vector3f thrust_body{
      setpoint.thrust_body[0],
      setpoint.thrust_body[1],
      setpoint.thrust_body[2]};
    _rates_setpoint->update(rates_sp, thrust_body);
  }

  inline void applyAccRatesSetpoint(const px4_msgs::msg::VehicleThrustAccSetpoint& setpoint)
  {
    const Eigen::Vector3f rates_sp{
      setpoint.rates_sp[0],
      setpoint.rates_sp[1],
      setpoint.rates_sp[2]};
    _acc_rates_setpoint->update(setpoint.thrust_acc_sp, rates_sp);
  }
};