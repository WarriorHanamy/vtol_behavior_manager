// Copyright (c) 2025, Differential Robotics
// All rights reserved.
// SPDX-License-Identifier: BSD-3-Clause
//
// Neural Gate Node
//
// A single-file ROS2 node with three responsibilities:
// 1. Publish /neural/target continuously (current position + offset).
// 2. Listen to RC trigger (button or aux1).
// 3. Forward /neural/control to PX4 only when the trigger is active and
//    neural control messages are fresh.
//
// Parameters:
//   trigger_source (string): "button" or "aux1"
//   button_mask (int): bitmask for button trigger (default 1024)
//   aux1_on_threshold (double): aux1 value above which gate opens (default 0.6)
//   aux1_off_threshold (double): aux1 value below which gate closes (default 0.4)
//   neural_control_timeout_s (double): max age of /neural/control to be valid
//   target_offset (vector<double>): [x, y, z] offset added to current position

#include <rclcpp/rclcpp.hpp>

#include <px4_msgs/msg/manual_control_setpoint.hpp>
#include <px4_msgs/msg/trajectory_setpoint.hpp>
#include <px4_msgs/msg/vehicle_acc_rates_setpoint.hpp>
#include <px4_msgs/msg/vehicle_odometry.hpp>

#include <array>
#include <cmath>
#include <cstdint>

class NeuralGateNode : public rclcpp::Node {
 public:
  NeuralGateNode() : Node("neural_gate") {
    // Parameters
    this->declare_parameter<std::string>("trigger_source", "aux1");
    this->declare_parameter<int>("button_mask", 1024);
    this->declare_parameter<double>("aux1_on_threshold", 0.6);
    this->declare_parameter<double>("aux1_off_threshold", 0.4);
    this->declare_parameter<double>("neural_control_timeout_s", 0.5);
    this->declare_parameter<std::vector<double>>("target_offset",
                                                  {0.0, 0.0, 0.0});

    trigger_source_ =
        this->get_parameter("trigger_source").as_string();
    button_mask_ =
        static_cast<uint16_t>(this->get_parameter("button_mask").as_int());
    aux1_on_threshold_ =
        this->get_parameter("aux1_on_threshold").as_double();
    aux1_off_threshold_ =
        this->get_parameter("aux1_off_threshold").as_double();
    neural_control_timeout_s_ =
        this->get_parameter("neural_control_timeout_s").as_double();

    std::vector<double> offset_param =
        this->get_parameter("target_offset").as_double_array();
    if (offset_param.size() == 3) {
      target_offset_ = {offset_param[0], offset_param[1], offset_param[2]};
    } else {
      RCLCPP_WARN(this->get_logger(),
                  "target_offset must have 3 elements, using default [0,0,0]");
      target_offset_ = {0.0, 0.0, 0.0};
    }

    // Publishers
    target_pub_ =
        this->create_publisher<px4_msgs::msg::TrajectorySetpoint>(
            "/neural/target", 10);
    control_pub_ =
        this->create_publisher<px4_msgs::msg::VehicleAccRatesSetpoint>(
            "/fmu/in/vehicle_acc_rates_setpoint", 1);

    // Subscribers
    odom_sub_ = this->create_subscription<px4_msgs::msg::VehicleOdometry>(
        "/fmu/out/vehicle_odometry", rclcpp::SensorDataQoS(),
        [this](const px4_msgs::msg::VehicleOdometry::SharedPtr msg) {
          ned_position_[0] = msg->position[0];
          ned_position_[1] = msg->position[1];
          ned_position_[2] = msg->position[2];
          position_valid_ = true;
        });

    rc_sub_ = this->create_subscription<px4_msgs::msg::ManualControlSetpoint>(
        "/fmu/out/manual_control_setpoint", rclcpp::SensorDataQoS(),
        [this](const px4_msgs::msg::ManualControlSetpoint::SharedPtr msg) {
          rc_valid_ = msg->valid;
          rc_aux1_ = msg->aux1;
          rc_buttons_ = msg->buttons;
        });

    neural_control_sub_ =
        this->create_subscription<px4_msgs::msg::VehicleAccRatesSetpoint>(
            "/neural/control", 10,
            [this](const px4_msgs::msg::VehicleAccRatesSetpoint::SharedPtr
                       msg) {
              last_neural_control_msg_ = *msg;
              has_neural_control_ = true;
              last_neural_control_time_ = this->get_clock()->now();
            });

    // 50 Hz timer
    timer_ = this->create_wall_timer(
        std::chrono::milliseconds(20),
        [this]() { tick(); });

    RCLCPP_INFO(this->get_logger(), "NeuralGate node initialized");
    RCLCPP_INFO(this->get_logger(), "  trigger_source: %s",
                trigger_source_.c_str());
    RCLCPP_INFO(this->get_logger(), "  target_offset: [%.2f, %.2f, %.2f]",
                target_offset_[0], target_offset_[1], target_offset_[2]);
  }

 private:
  bool isNeuralControlFresh() {
    if (!has_neural_control_) return false;
    auto elapsed =
        (this->get_clock()->now() - last_neural_control_time_).seconds();
    return elapsed < neural_control_timeout_s_;
  }

  bool evaluateTrigger() {
    if (!rc_valid_) return false;

    if (trigger_source_ == "button") {
      return (rc_buttons_ & button_mask_) == button_mask_;
    }

    if (trigger_source_ == "aux1") {
      if (rc_aux1_ > static_cast<float>(aux1_on_threshold_)) return true;
      if (rc_aux1_ < static_cast<float>(aux1_off_threshold_)) return false;
      // Hysteresis: keep current state when in deadband
      return gate_open_;
    }

    RCLCPP_WARN(this->get_logger(), "Unknown trigger_source: %s",
                trigger_source_.c_str());
    return false;
  }

  void publishTarget() {
    px4_msgs::msg::TrajectorySetpoint msg;
    msg.timestamp =
        static_cast<uint64_t>(this->get_clock()->now().nanoseconds() / 1000);
    msg.position[0] =
        static_cast<float>(ned_position_[0] + target_offset_[0]);
    msg.position[1] =
        static_cast<float>(ned_position_[1] + target_offset_[1]);
    msg.position[2] =
        static_cast<float>(ned_position_[2] + target_offset_[2]);
    msg.velocity[0] = NAN;
    msg.velocity[1] = NAN;
    msg.velocity[2] = NAN;
    msg.acceleration[0] = NAN;
    msg.acceleration[1] = NAN;
    msg.acceleration[2] = NAN;
    target_pub_->publish(msg);
  }

  void tick() {
    if (position_valid_) {
      publishTarget();
    }

    bool trigger_active = evaluateTrigger();
    bool neural_fresh = isNeuralControlFresh();
    bool should_be_open = trigger_active && neural_fresh;

    if (should_be_open && !gate_open_) {
      RCLCPP_INFO(this->get_logger(), "Gate OPENED");
    } else if (!should_be_open && gate_open_) {
      RCLCPP_INFO(this->get_logger(), "Gate CLOSED");
    }

    gate_open_ = should_be_open;

    if (gate_open_ && has_neural_control_) {
      control_pub_->publish(last_neural_control_msg_);
    }
  }

  // Parameters
  std::string trigger_source_;
  uint16_t button_mask_;
  double aux1_on_threshold_;
  double aux1_off_threshold_;
  double neural_control_timeout_s_;
  std::array<double, 3> target_offset_;

  // State
  bool position_valid_ = false;
  std::array<double, 3> ned_position_{0.0, 0.0, 0.0};

  bool rc_valid_ = false;
  float rc_aux1_ = 0.0f;
  uint16_t rc_buttons_ = 0;

  bool gate_open_ = false;
  bool has_neural_control_ = false;
  rclcpp::Time last_neural_control_time_;
  px4_msgs::msg::VehicleAccRatesSetpoint last_neural_control_msg_;

  // ROS interfaces
  rclcpp::Publisher<px4_msgs::msg::TrajectorySetpoint>::SharedPtr target_pub_;
  rclcpp::Publisher<px4_msgs::msg::VehicleAccRatesSetpoint>::SharedPtr
      control_pub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleOdometry>::SharedPtr odom_sub_;
  rclcpp::Subscription<px4_msgs::msg::ManualControlSetpoint>::SharedPtr rc_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleAccRatesSetpoint>::SharedPtr
      neural_control_sub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<NeuralGateNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
