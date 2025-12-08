/****************************************************************************
 * Copyright (c) 2023 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/
#pragma once

#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/experimental/acc_rates.hpp>
#include <px4_ros2/odometry/local_position.hpp>
#include <px4_msgs/msg/vehicle_thrust_acc_setpoint.hpp>
#include <std_msgs/msg/bool.hpp>
#include <rclcpp/rclcpp.hpp>
#include <Eigen/Core>

/**
 * @class NeuralCtrlMode
 * @brief High-performance neural network controlled flight mode with acceleration rates setpoint handling
 *
 * Supported control mode: AccRates
 */
class NeuralCtrlMode : public px4_ros2::ModeBase
{
public:
  explicit NeuralCtrlMode(rclcpp::Node &arg_node)
      : ModeBase(arg_node, Settings{"NeuralControl"})
  {
    _activation_time = {0};
    _has_neural_setpoint = false;

    _node.declare_parameter("neural_setpoint_timeout", 0.05);
    _neural_setpoint_timeout = _node.get_parameter("neural_setpoint_timeout").as_double();

    _acc_rates_setpoint = std::make_shared<px4_ros2::AccRatesSetpointType>(*this);
    _odometry_local_position = std::make_shared<px4_ros2::OdometryLocalPosition>(*this);
    _manual_control_input = std::make_shared<px4_ros2::ManualControlInput>(*this);

    subscribeToNeuralSetpoint();

    _stop_neural_ctrl_sub = _node.create_subscription<std_msgs::msg::Bool>(
        "/neural/stop_control", 10,
        [this](const std_msgs::msg::Bool::SharedPtr msg)
        {
          if (msg->data)
          {
            RCLCPP_INFO(_node.get_logger(), "Neural: Stop control command received");
            completed(px4_ros2::Result::Success);
          }
        });

    _start_neural_ctrl_pub = _node.create_publisher<std_msgs::msg::Bool>(
        "/neural/mode_neural_ctrl", 10);
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

    auto msg = std_msgs::msg::Bool();
    msg.data = true;
    _start_neural_ctrl_pub->publish(msg);
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
  // Hot path data (cache locality optimization)
  px4_msgs::msg::VehicleThrustAccSetpoint _neural_setpoint;
  rclcpp::Time _neural_setpoint_timestamp;

  std::shared_ptr<px4_ros2::ManualControlInput> _manual_control_input;
  std::shared_ptr<px4_ros2::AccRatesSetpointType> _acc_rates_setpoint;
  std::shared_ptr<px4_ros2::OdometryLocalPosition> _odometry_local_position;

  // Configuration
  float _neural_setpoint_timeout;
  double _activation_time;
  bool _has_neural_setpoint;

  // ROS2 communication
  rclcpp::Subscription<px4_msgs::msg::VehicleThrustAccSetpoint>::SharedPtr _acc_rates_sub;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr _stop_neural_ctrl_sub;
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr _start_neural_ctrl_pub;

  void subscribeToNeuralSetpoint()
  {
    _acc_rates_sub = _node.create_subscription<px4_msgs::msg::VehicleThrustAccSetpoint>(
        "/neural/setpoint", 10,
        [this](const px4_msgs::msg::VehicleThrustAccSetpoint::SharedPtr msg) {
          _neural_setpoint = *msg;
          _neural_setpoint_timestamp = _node.get_clock()->now();
          _has_neural_setpoint = true;
        });
    RCLCPP_INFO(_node.get_logger(), "Neural: Subscribed to AccRates setpoint");
  }

  inline void processNeuralSetpoint()
  {
    if (!_has_neural_setpoint) [[unlikely]] {
      RCLCPP_INFO_THROTTLE(_node.get_logger(), *_node.get_clock(), 1000,
                           "Neural: Waiting for setpoint...");
      return;
    }

    const float time_since_setpoint = (_node.get_clock()->now() - _neural_setpoint_timestamp).seconds();
    if (time_since_setpoint > _neural_setpoint_timeout) [[unlikely]] {
      RCLCPP_ERROR(_node.get_logger(),
                   "Neural: Setpoint timeout (%.3fs)", time_since_setpoint);
      completed(px4_ros2::Result::ModeFailureOther);
      return;
    }

    applyAccRatesSetpoint(_neural_setpoint);
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