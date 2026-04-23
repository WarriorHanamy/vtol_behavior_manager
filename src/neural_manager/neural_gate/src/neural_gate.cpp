// Copyright (c) 2025, Differential Robotics
// All rights reserved.
// SPDX-License-Identifier: BSD-3-Clause
//
// Neural Gate Node
//
// A single-file ROS2 node with two responsibilities:
// 1. Publish /neural/target when in POSCTL mode (current position + offset).
// 2. Listen to RC trigger (button and aux1) to switch to offboard mode.
//
// State machine based on VehicleStatus nav_state:
//   - POSCTL: publish target, allow trigger to switch to offboard
//   - OFFBOARD: do nothing, neural network is in control
//   - default: WARN, do nothing
//
// Parameters:
//   button_mask (int): bitmask for button trigger (default 1024)
//   aux1_on_threshold (double): aux1 value above which trigger activates (default 0.6)
//   aux1_off_threshold (double): aux1 value below which trigger deactivates (default 0.4)
//   target_offset (vector<double>): [x, y, z] offset added to current position

#include <rclcpp/rclcpp.hpp>

#include <px4_msgs/msg/manual_control_setpoint.hpp>
#include <px4_msgs/msg/offboard_control_mode.hpp>
#include <px4_msgs/msg/trajectory_setpoint.hpp>
#include <px4_msgs/msg/vehicle_command.hpp>
#include <px4_msgs/msg/vehicle_command_ack.hpp>
#include <px4_msgs/msg/vehicle_odometry.hpp>
#include <px4_msgs/msg/vehicle_status.hpp>

#include <array>
#include <cmath>
#include <cstdint>

class NeuralGateNode : public rclcpp::Node {
public:
  NeuralGateNode() : Node("neural_gate") {
    // Parameters
    this->declare_parameter<int>("button_mask", 1024);
    this->declare_parameter<double>("aux1_on_threshold", 0.6);
    this->declare_parameter<double>("aux1_off_threshold", 0.4);
    this->declare_parameter<std::vector<double>>("target_offset",
                                                 {0.0, 0.0, 0.0});

    button_mask_ =
        static_cast<uint16_t>(this->get_parameter("button_mask").as_int());
    aux1_on_threshold_ = this->get_parameter("aux1_on_threshold").as_double();
    aux1_off_threshold_ = this->get_parameter("aux1_off_threshold").as_double();

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
    target_pub_ = this->create_publisher<px4_msgs::msg::TrajectorySetpoint>(
        "/neural/target", 10);
    offboard_mode_pub_ =
        this->create_publisher<px4_msgs::msg::OffboardControlMode>(
            "/fmu/in/offboard_control_mode", 1);
    vehicle_cmd_pub_ = this->create_publisher<px4_msgs::msg::VehicleCommand>(
        "/fmu/in/vehicle_command", 1);

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

    vehicle_status_sub_ =
        this->create_subscription<px4_msgs::msg::VehicleStatus>(
            "/fmu/out/vehicle_status_v1", rclcpp::SensorDataQoS(),
            [this](const px4_msgs::msg::VehicleStatus::SharedPtr msg) {
              px4_nav_state_ = msg->nav_state;
              has_vehicle_status_ = true;
            });

    vehicle_command_ack_sub_ =
        this->create_subscription<px4_msgs::msg::VehicleCommandAck>(
            "/fmu/out/vehicle_command_ack", rclcpp::SensorDataQoS(),
            [this](const px4_msgs::msg::VehicleCommandAck::SharedPtr msg) {
              if (msg->command ==
                  px4_msgs::msg::VehicleCommand::VEHICLE_CMD_DO_SET_MODE) {
                if (msg->result ==
                    px4_msgs::msg::VehicleCommandAck::VEHICLE_CMD_RESULT_ACCEPTED) {
                  RCLCPP_INFO(this->get_logger(),
                              "[GATE] Offboard mode confirmed via ACK");
                } else {
                  RCLCPP_WARN(this->get_logger(),
                              "[GATE] Offboard mode command rejected: %d",
                              msg->result);
                }
              }
            });

    // 400 Hz timer (2.5ms)
    timer_ = this->create_wall_timer(std::chrono::microseconds(2500),
                                     [this]() { tick(); });

    // 10 Hz timer for offboard heartbeat (unconditional)
    offboard_heartbeat_timer_ =
        this->create_wall_timer(std::chrono::milliseconds(100),
                                [this]() { publishOffboardHeartbeat(); });

    RCLCPP_INFO(this->get_logger(), "[GATE] NeuralGate node initialized");
    RCLCPP_INFO(this->get_logger(), "[GATE]   target_offset: [%.2f, %.2f, %.2f]",
                target_offset_[0], target_offset_[1], target_offset_[2]);
  }

private:
  int64_t nowNanoseconds() { return this->get_clock()->now().nanoseconds(); }

  bool evaluateTrigger() {
    if (!rc_valid_) {
      prev_button_active_ = false;
      prev_aux1_active_ = false;
      return false;
    }

    bool button_active = (rc_buttons_ & button_mask_) == button_mask_;
    bool button_edge = button_active && !prev_button_active_;
    prev_button_active_ = button_active;

    bool aux1_active;
    if (rc_aux1_ > static_cast<float>(aux1_on_threshold_)) {
      aux1_active = true;
    } else if (rc_aux1_ < static_cast<float>(aux1_off_threshold_)) {
      aux1_active = false;
    } else {
      aux1_active = prev_aux1_active_;
    }
    bool aux1_edge = aux1_active && !prev_aux1_active_;
    prev_aux1_active_ = aux1_active;

    return button_edge || aux1_edge;
  }

  void publishTarget() {
    px4_msgs::msg::TrajectorySetpoint msg;
    msg.timestamp =
        static_cast<uint64_t>(this->get_clock()->now().nanoseconds() / 1000);
    msg.position[0] = static_cast<float>(ned_position_[0] + target_offset_[0]);
    msg.position[1] = static_cast<float>(ned_position_[1] + target_offset_[1]);
    msg.position[2] = static_cast<float>(ned_position_[2] + target_offset_[2]);
    msg.velocity[0] = NAN;
    msg.velocity[1] = NAN;
    msg.velocity[2] = NAN;
    msg.acceleration[0] = NAN;
    msg.acceleration[1] = NAN;
    msg.acceleration[2] = NAN;
    target_pub_->publish(msg);
  }

  void publishOffboardHeartbeat() {
    px4_msgs::msg::OffboardControlMode msg;
    msg.timestamp =
        static_cast<uint64_t>(this->get_clock()->now().nanoseconds() / 1000);
    msg.position = false;
    msg.velocity = false;
    msg.acceleration = false;
    msg.attitude = false;
    msg.body_rate = true;
    msg.thrust_and_torque = true;
    msg.direct_actuator = true;
    offboard_mode_pub_->publish(msg);
  }

  void publishOffboardModeCommand() {
    px4_msgs::msg::VehicleCommand msg;
    msg.timestamp =
        static_cast<uint64_t>(this->get_clock()->now().nanoseconds() / 1000);
    msg.command = px4_msgs::msg::VehicleCommand::VEHICLE_CMD_DO_SET_MODE;
    msg.param1 = 1.0f; // MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
    msg.param2 = 6.0f; // PX4_CUSTOM_MAIN_MODE_OFFBOARD
    msg.target_system = 1;
    msg.target_component = 1;
    msg.source_system = 1;
    msg.source_component = 1;
    msg.from_external = true;
    vehicle_cmd_pub_->publish(msg);
  }

  void tick() {
    bool trigger_edge = evaluateTrigger();

    switch (px4_nav_state_) {
      case px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_POSCTL:
        if (position_valid_) {
          RCLCPP_INFO_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                               "[GATE] POSCTL - publishing /neural/target");
          publishTarget();
        } else {
          RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                               "[GATE] POSCTL - waiting for odometry");
        }
        if (trigger_edge) {
          publishOffboardModeCommand();
        }
        break;

      case px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_OFFBOARD:
        // Neural network is in control, do nothing
        break;

      default:
        RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                             "[GATE] current mode is %d, not supported",
                             px4_nav_state_);
        break;
    }
  }

  // Parameters
  uint16_t button_mask_;
  double aux1_on_threshold_;
  double aux1_off_threshold_;
  std::array<double, 3> target_offset_;

  // State
  bool position_valid_ = false;
  std::array<double, 3> ned_position_{0.0, 0.0, 0.0};

  bool rc_valid_ = false;
  float rc_aux1_ = 0.0f;
  uint16_t rc_buttons_ = 0;

  bool prev_button_active_ = false;
  bool prev_aux1_active_ = false;
  bool has_vehicle_status_ = false;
  uint8_t px4_nav_state_ = 0;

  // ROS interfaces
  rclcpp::Publisher<px4_msgs::msg::TrajectorySetpoint>::SharedPtr target_pub_;
  rclcpp::Publisher<px4_msgs::msg::OffboardControlMode>::SharedPtr
      offboard_mode_pub_;
  rclcpp::Publisher<px4_msgs::msg::VehicleCommand>::SharedPtr vehicle_cmd_pub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleOdometry>::SharedPtr odom_sub_;
  rclcpp::Subscription<px4_msgs::msg::ManualControlSetpoint>::SharedPtr rc_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr
      vehicle_status_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleCommandAck>::SharedPtr
      vehicle_command_ack_sub_;
  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::TimerBase::SharedPtr offboard_heartbeat_timer_;
};

int main(int argc, char *argv[]) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<NeuralGateNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
