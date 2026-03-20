/****************************************************************************
 * Copyright (c) 2023 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/
#pragma once

#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/experimental/acc_rates.hpp>
#include <px4_ros2/odometry/local_position.hpp>
#include <px4_msgs/msg/vehicle_acc_rates_setpoint.hpp>
#include <std_msgs/msg/bool.hpp>
#include <rclcpp/rclcpp.hpp>
#include <Eigen/Core>

/**
 * @class NeuralCtrlMode
 * @brief Neural network controlled flight mode using AccRatesSetpoint
 *        (thrust acceleration + body rates)
 */
class NeuralCtrlMode : public px4_ros2::ModeBase
{
public:
  explicit NeuralCtrlMode(rclcpp::Node &arg_node)
      : ModeBase(arg_node, Settings{"NeuralControl"})
  {
    _activation_time = {0};
    _has_neural_setpoint = false;
    _startup_position_set = false;

    _acc_rates_setpoint = std::make_shared<px4_ros2::AccRatesSetpointType>(*this);
    RCLCPP_INFO(_node.get_logger(), "Neural: Thrust-axis Acceleration + Body Rates (AccRatesSetpoint)");

    _manual_control_input = std::make_shared<px4_ros2::ManualControlInput>(*this);
    _odometry_position = std::make_shared<px4_ros2::OdometryLocalPosition>(*this);

    node().declare_parameter("geofence_xy_limit", 5.0f);
    node().declare_parameter("geofence_z_limit", 0.5f);
    node().declare_parameter("neural_mode_timeout", 0.1f);
    _geofence_xy_limit = node().get_parameter("geofence_xy_limit").as_double();
    _geofence_z_limit = node().get_parameter("geofence_z_limit").as_double();
    _neural_mode_timeout = node().get_parameter("neural_mode_timeout").as_double();

    subscribeToNeuralControl();
  }

  ~NeuralCtrlMode() override = default;
  
  NeuralCtrlMode(const NeuralCtrlMode&) = delete;
  NeuralCtrlMode& operator=(const NeuralCtrlMode&) = delete;
  NeuralCtrlMode(NeuralCtrlMode&&) noexcept = default;
  NeuralCtrlMode& operator=(NeuralCtrlMode&&) noexcept = default;

protected:
  void onActivate() override
  {
    _activation_time = _node.get_clock()->now().seconds();
    _has_neural_setpoint = false;
    _startup_position_set = false;
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

    if (checkGeofenceExceeded()) {
      completed(px4_ros2::Result::ModeFailureOther);
      return;
    }

    processNeuralSetpoint();
  }

private:
  px4_msgs::msg::VehicleAccRatesSetpoint _neural_acc_rates_ctrl;
  rclcpp::Time _neural_ctrl_timestamp;

  std::shared_ptr<px4_ros2::ManualControlInput> _manual_control_input;
  std::shared_ptr<px4_ros2::AccRatesSetpointType> _acc_rates_setpoint;
  std::shared_ptr<px4_ros2::OdometryLocalPosition> _odometry_position;

  double _activation_time;
  bool _has_neural_setpoint;

  Eigen::Vector3f _startup_position{0, 0, 0};
  bool _startup_position_set{false};
  float _geofence_xy_limit{5.0f};
  float _geofence_z_limit{0.5f};
  float _neural_mode_timeout{0.1f};

  rclcpp::Subscription<px4_msgs::msg::VehicleAccRatesSetpoint>::SharedPtr _neural_acc_rates_ctrl_sub;

  bool checkGeofenceExceeded()
  {
    if (!_odometry_position->positionXYValid() || !_odometry_position->positionZValid()) {
      return false;
    }

    if (!_startup_position_set) {
      _startup_position = _odometry_position->positionNed();
      _startup_position_set = true;
      RCLCPP_INFO(_node.get_logger(), "Geofence center set: (%.2f, %.2f, %.2f)",
                  _startup_position.x(), _startup_position.y(), _startup_position.z());
      return false;
    }

    auto pos = _odometry_position->positionNed();
    float xy_dist = (pos.head<2>() - _startup_position.head<2>()).norm();
    float z_dist = std::abs(pos.z() - _startup_position.z());

    if (xy_dist > _geofence_xy_limit || z_dist > _geofence_z_limit) {
      RCLCPP_WARN(_node.get_logger(), "Geofence exceeded: XY=%.2fm/%.1fm, Z=%.2fm/%.1fm",
                  xy_dist, _geofence_xy_limit, z_dist, _geofence_z_limit);
      return true;
    }
    return false;
  }

  // TODO, the naming is not clear.
  void subscribeToNeuralControl()
  {
    _neural_acc_rates_ctrl_sub = _node.create_subscription<px4_msgs::msg::VehicleAccRatesSetpoint>(
        "/neural/control", rclcpp::SensorDataQoS(),
        [this](const px4_msgs::msg::VehicleAccRatesSetpoint::SharedPtr msg) {
          _neural_acc_rates_ctrl = *msg;
          _neural_ctrl_timestamp = _node.get_clock()->now();
          _has_neural_setpoint = true;
        });
    RCLCPP_INFO(_node.get_logger(), "Neural: Subscribed to /neural/control (VehicleThrustAccSetpoint)");
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

    applyAccRatesSetpoint(_neural_acc_rates_ctrl);
  }

  // TODO, I'm not quite clear this if should do post-processing here.
  inline void applyAccRatesSetpoint(const px4_msgs::msg::VehicleAccRatesSetpoint& setpoint)
  {
    const Eigen::Vector3f rates_sp{
      setpoint.rates_sp[0],
      setpoint.rates_sp[1],
      setpoint.rates_sp[2]};
    _acc_rates_setpoint->update(setpoint.thrust_axis_acc_sp, rates_sp);
  }
};
