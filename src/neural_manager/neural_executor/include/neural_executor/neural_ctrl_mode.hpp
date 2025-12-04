/****************************************************************************
 * Copyright (c) 2023 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/
#pragma once

#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/multicopter/goto.hpp>
#include <px4_ros2/control/setpoint_types/experimental/rates.hpp>
#include <px4_ros2/control/setpoint_types/experimental/acc_rates.hpp>
#include <px4_ros2/odometry/local_position.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <std_msgs/msg/bool.hpp>
#include <rclcpp/rclcpp.hpp>
#include <Eigen/Core>
#include <variant>

// Compile-time control mode selection
// #define USE_GOTO_CTRL
#define USE_RATES_CTRL
// #define USE_ACC_RATES_CTRL

// Compile-time check: Ensure exactly one control mode is defined
#if defined(USE_GOTO_CTRL) + defined(USE_RATES_CTRL) + defined(USE_ACC_RATES_CTRL) != 1
#error "Exactly one control mode must be defined: USE_GOTO_CTRL, USE_RATES_CTRL, or USE_ACC_RATES_CTRL"
#endif

// Neural control setpoint types - Type as Documentation
using NeuralGotoSetpoint = geometry_msgs::msg::PoseStamped;
using NeuralRatesSetpoint = px4_msgs::msg::VehicleRatesSetpoint;
using NeuralAccRatesSetpoint = px4_msgs::msg::VehicleThrustAccSetpoint;

// Unified setpoint type using std::variant for type-safe dispatching
using NeuralControlSetpoint = std::variant<
    NeuralGotoSetpoint,
    NeuralRatesSetpoint,
    NeuralAccRatesSetpoint>;

// Neural setpoint type enumeration
enum class NeuralSetpointType : uint8_t {
    Goto,
    Rates,
    AccRates
};

/**
 * @class NeuralCtrlMode
 * @brief High-performance neural network controlled flight mode with type-safe setpoint handling
 * 
 * Supported control modes: Goto | Rates | AccRates (compile-time selected)
 */
class NeuralCtrlMode : public px4_ros2::ModeBase
{
public:
  explicit NeuralCtrlMode(rclcpp::Node &arg_node)
      : ModeBase(arg_node, Settings{"NeuralControl"})
  {
    _activation_time = {0};
    _has_neural_setpoint = false;
    
#ifdef USE_GOTO_CTRL
    _setpoint_type = NeuralSetpointType::Goto;
#elif defined(USE_RATES_CTRL)
    _setpoint_type = NeuralSetpointType::Rates;
#elif defined(USE_ACC_RATES_CTRL)
    _setpoint_type = NeuralSetpointType::AccRates;
#endif

    _node.declare_parameter("neural_setpoint_timeout", 0.05);
    _neural_setpoint_timeout = _node.get_parameter("neural_setpoint_timeout").as_double();

    _goto_setpoint = std::make_shared<px4_ros2::MulticopterGotoSetpointType>(*this);
    _rates_setpoint = std::make_shared<px4_ros2::RatesSetpointType>(*this);
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
  NeuralControlSetpoint _neural_setpoint;
  rclcpp::Time _neural_setpoint_timestamp;
  
  std::shared_ptr<px4_ros2::ManualControlInput> _manual_control_input;
  std::shared_ptr<px4_ros2::MulticopterGotoSetpointType> _goto_setpoint;
  std::shared_ptr<px4_ros2::RatesSetpointType> _rates_setpoint;
  std::shared_ptr<px4_ros2::AccRatesSetpointType> _acc_rates_setpoint;
  std::shared_ptr<px4_ros2::OdometryLocalPosition> _odometry_local_position;

  // Configuration
  NeuralSetpointType _setpoint_type;
  float _neural_setpoint_timeout;
  double _activation_time;
  bool _has_neural_setpoint;

  // ROS2 communication
  rclcpp::Subscription<NeuralGotoSetpoint>::SharedPtr _goto_sub;
  rclcpp::Subscription<NeuralRatesSetpoint>::SharedPtr _rates_sub;
  rclcpp::Subscription<NeuralAccRatesSetpoint>::SharedPtr _acc_rates_sub;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr _stop_neural_ctrl_sub;
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr _start_neural_ctrl_pub;

  template<typename T>
  void createSubscriptionHelper(
      typename rclcpp::Subscription<T>::SharedPtr& sub_ptr,
      const std::string& mode_name)
  {
    sub_ptr = _node.create_subscription<T>(
        "/neural/setpoint", 10,
        [this](const typename T::SharedPtr msg) {
          _neural_setpoint = *msg;
          _neural_setpoint_timestamp = _node.get_clock()->now();
          _has_neural_setpoint = true;
        });
    RCLCPP_INFO(_node.get_logger(), "Neural: Subscribed to %s setpoint", mode_name.c_str());
  }

  void subscribeToNeuralSetpoint()
  {
    switch (_setpoint_type) {
      case NeuralSetpointType::Goto:
        createSubscriptionHelper<NeuralGotoSetpoint>(_goto_sub, "Goto");
        break;
      case NeuralSetpointType::Rates:
        createSubscriptionHelper<NeuralRatesSetpoint>(_rates_sub, "Rates");
        break;
      case NeuralSetpointType::AccRates:
        createSubscriptionHelper<NeuralAccRatesSetpoint>(_acc_rates_sub, "AccRates");
        break;
    }
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

    std::visit([this](auto&& setpoint) {
      using T = std::decay_t<decltype(setpoint)>;
      if constexpr (std::is_same_v<T, NeuralGotoSetpoint>) {
        applyGotoSetpoint(setpoint);
      } else if constexpr (std::is_same_v<T, NeuralRatesSetpoint>) {
        applyRatesSetpoint(setpoint);
      } else if constexpr (std::is_same_v<T, NeuralAccRatesSetpoint>) {
        applyAccRatesSetpoint(setpoint);
      }
    }, _neural_setpoint);
  }

  inline void applyGotoSetpoint(const NeuralGotoSetpoint& setpoint)
  {
    if (!_odometry_local_position->positionXYValid() || 
        !_odometry_local_position->positionZValid()) [[unlikely]] {
      RCLCPP_ERROR(_node.get_logger(), "Neural: Position data invalid");
      completed(px4_ros2::Result::ModeFailureOther);
      return;
    }

    const Eigen::Vector3f target{
        static_cast<float>(setpoint.pose.position.x),
        static_cast<float>(setpoint.pose.position.y),
        static_cast<float>(setpoint.pose.position.z)};

    _goto_setpoint->update(target, std::nullopt, 2.0f, 2.0f, std::nullopt);
  }

  inline void applyRatesSetpoint(const NeuralRatesSetpoint& setpoint)
  {
    const Eigen::Vector3f rates_sp{setpoint.roll, setpoint.pitch, setpoint.yaw};
    const Eigen::Vector3f thrust_sp{
        setpoint.thrust_body[0],
        setpoint.thrust_body[1],
        setpoint.thrust_body[2]};
    _rates_setpoint->update(rates_sp, thrust_sp);
  }

  inline void applyAccRatesSetpoint(const NeuralAccRatesSetpoint& setpoint)
  {
  const Eigen::Vector3f rates_sp{
    setpoint.rates_sp[0],
    setpoint.rates_sp[1],
    setpoint.rates_sp[2]};
  _acc_rates_setpoint->update(setpoint.thrust_acc_sp, rates_sp);
  }
};