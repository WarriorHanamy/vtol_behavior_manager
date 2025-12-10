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
using NeuralCtrlMsg = px4_msgs::msg::VehicleThrustAccSetpoint;
public:
  explicit NeuralCtrlMode(rclcpp::Node &arg_node)
      : ModeBase(arg_node, Settings{"NeuralControl"})
  {
    _activation_time = {0};
    _has_neural_setpoint = false;

    _acc_rates_setpoint = std::make_shared<px4_ros2::AccRatesSetpointType>(*this);
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
  // Hot path data (cache locality optimization)
  NeuralCtrlMsg _neural_ctrl;
  rclcpp::Time _neural_ctrl_timestamp;

  std::shared_ptr<px4_ros2::ManualControlInput> _manual_control_input;
  std::shared_ptr<px4_ros2::AccRatesSetpointType> _acc_rates_setpoint;
  double _activation_time;
  bool _has_neural_setpoint;

  // ROS2 communication
  rclcpp::Subscription<NeuralCtrlMsg>::SharedPtr _neural_ctrl_sub;
  void subscribeToNeuralControl()
  {
    _neural_ctrl_sub = _node.create_subscription<NeuralCtrlMsg>(
        "/neural/control", rclcpp::SensorDataQoS(),
        [this](const NeuralCtrlMsg::SharedPtr msg) {
          _neural_ctrl = *msg;
          _neural_ctrl_timestamp = _node.get_clock()->now();
          _has_neural_setpoint = true;
          
        });
    RCLCPP_INFO(_node.get_logger(), "Neural: Subscribed to NeuralControl");
  }

  inline void processNeuralSetpoint()
  {
    if (!_has_neural_setpoint) [[unlikely]] {
      RCLCPP_INFO_THROTTLE(_node.get_logger(), *_node.get_clock(), 1000,
                           "Neural: Waiting for setpoint...");
      return;
    }

    // const float time_since_activation = (_node.get_clock()->now().seconds() - _activation_time);
    // if (time_since_activation > 1.0f) [[unlikely]] {
    //   RCLCPP_ERROR(_node.get_logger(),
    //                "Neural Control timeout (%.3fs)", time_since_activation);
    //   completed(px4_ros2::Result::ModeFailureOther);
    //   return;
    // }
    RCLCPP_WARN_THROTTLE(_node.get_logger(), *_node.get_clock(), 1000,
                         "Neural: Applying setpoint...");
    _neural_ctrl.rates_sp[2] = 0.0f;
    applyAccRatesSetpoint(_neural_ctrl);
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