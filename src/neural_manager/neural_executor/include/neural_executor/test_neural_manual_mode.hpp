/****************************************************************************
 * Copyright (c) 2025 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/
/**
 * @file test_neural_manual_mode.hpp
 * @brief Manual flight mode with RC control and exit detection via aux1/button
 * @author steven cheng
 * @date created on 2025.03.20
 */

#pragma once

#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/experimental/acc_rates.hpp>
#include <px4_ros2/odometry/attitude.hpp>
#include <rclcpp/rclcpp.hpp>
#include <yaml-cpp/yaml.h>
#include <Eigen/Core>

/**
 * @class TestNeuralManualMode
 * @brief Manual flight mode with RC control and exit detection
 *
 * This mode converts RC stick inputs into acceleration and rate setpoints.
 * Exit conditions: aux1 falling edge or button released
 *
 * Coordinate Frames:
 * - World Frame: NED (North-East-Down)
 * - Baselist Frame: FRD (Forward-Right-Down)
 * - Quaternion: Hamilton convention [w, x, y, z]
 *
 * Control Mode:
 * - Input: ManualControlInput (roll, pitch, yaw, throttle sticks)
 * - Output: AccRatesSetpoint (thrust acceleration + body rates)
 * - Yaw Control: Rate-based (direct stick input)
 * - Exit: aux1 falling edge OR button released
 */
class TestNeuralManualMode : public px4_ros2::ModeBase
{
  static constexpr uint16_t RC_NN_CMD_MASK = 1024;

public:
  explicit TestNeuralManualMode(rclcpp::Node & node)
      : ModeBase(node, Settings{"TestNeuralManual"})
  {
    loadConfigFromYaml();

    _manual_control_input = std::make_shared<px4_ros2::ManualControlInput>(*this);
    _attitude = std::make_shared<px4_ros2::OdometryAttitude>(*this);
    _acc_rates_setpoint = std::make_shared<px4_ros2::AccRatesSetpointType>(*this);

    RCLCPP_INFO(_node.get_logger(),
      "TestNeuralManualMode initialized: max_tilt=%.1f deg, max_acc=%.1f m/s^2, yaw_weight=%.2f",
      px4_ros2::radToDeg(_config.max_tilt_angle), _config.max_acc, _config.yaw_weight);
  }

  ~TestNeuralManualMode() override = default;

  TestNeuralManualMode(const TestNeuralManualMode&) = delete;
  TestNeuralManualMode& operator=(const TestNeuralManualMode&) = delete;
  TestNeuralManualMode(TestNeuralManualMode&&) noexcept = default;
  TestNeuralManualMode& operator=(TestNeuralManualMode&&) noexcept = default;

protected:
  void onActivate() override
  {
    _aux1_high_last = true;
    _button_pressed_last = true;
    RCLCPP_INFO(_node.get_logger(), "TestNeuralManualMode activated");
  }

  void onDeactivate() override
  {
    RCLCPP_INFO(_node.get_logger(), "TestNeuralManualMode deactivated");
  }

  void updateSetpoint(float dt_s) override
  {
    if (!_manual_control_input->isValid()) {
      RCLCPP_WARN_THROTTLE(_node.get_logger(), *_node.get_clock(), 1000,
        "TestNeuralManual: Waiting for valid manual control input...");
      return;
    }

    if (detectExitCondition()) {
      RCLCPP_INFO(_node.get_logger(), "TestNeuralManual: Exit triggered by RC");
      completed(px4_ros2::Result::ModeFailureOther);
      return;
    }

    if (!_attitude->lastValid(500ms)) {
      RCLCPP_WARN_THROTTLE(_node.get_logger(), *_node.get_clock(), 1000,
        "TestNeuralManual: Waiting for attitude data...");
      return;
    }

    const float stick_roll = _manual_control_input->roll();
    const float stick_pitch = _manual_control_input->pitch();
    const float stick_yaw = _manual_control_input->yaw();
    const float stick_throttle = _manual_control_input->throttle();

    const Eigen::Quaternionf q_current = _attitude->attitude();
    const Eigen::Quaternionf q_tilt = generateTiltSetpoint(stick_roll, stick_pitch);
    const float acc_sp = computeAccSetpoint(stick_throttle);
    const Eigen::Vector3f rates_sp = computeRateSetpoint(q_current, q_tilt, stick_yaw);

    _acc_rates_setpoint->update(acc_sp, rates_sp);

    RCLCPP_DEBUG_THROTTLE(_node.get_logger(), *_node.get_clock(), 500,
      "TestNeuralManual: sticks[%.2f,%.2f,%.2f,%.2f] -> acc=%.2f, rates[%.2f,%.2f,%.2f]",
      stick_roll, stick_pitch, stick_yaw, stick_throttle,
      acc_sp, rates_sp[0], rates_sp[1], rates_sp[2]);
  }

private:
  struct Config
  {
    float max_tilt_angle{0.785f};
    float max_acc{19.6f};
    float yaw_weight{0.5f};
    Eigen::Vector3f p_gains{5.0f, 5.0f, 3.0f};
    float max_rate{3.0f};
  };

  std::shared_ptr<px4_ros2::ManualControlInput> _manual_control_input;
  std::shared_ptr<px4_ros2::OdometryAttitude> _attitude;
  std::shared_ptr<px4_ros2::AccRatesSetpointType> _acc_rates_setpoint;
  Config _config;

  bool _aux1_high_last{true};
  bool _button_pressed_last{true};

  bool detectExitCondition()
  {
    bool aux1_high = _manual_control_input->aux1() > 0.5f;
    bool button_pressed = _manual_control_input->buttons() == RC_NN_CMD_MASK;

    bool aux1_falling = !aux1_high && _aux1_high_last;
    bool button_released = !button_pressed && _button_pressed_last;

    _aux1_high_last = aux1_high;
    _button_pressed_last = button_pressed;

    return aux1_falling || button_released;
  }

  void loadConfigFromYaml()
  {
    _config = Config{};

    std::string config_file;
    if (_node.get_parameter("config_file", config_file) && !config_file.empty()) {
      try {
        YAML::Node config = YAML::LoadFile(config_file);

        if (config["neural_manual"]) {
          auto node = config["neural_manual"];

          if (node["max_tilt_angle"]) {
            _config.max_tilt_angle = node["max_tilt_angle"].as<float>();
            if (_config.max_tilt_angle > 2.0f) {
              _config.max_tilt_angle = px4_ros2::degToRad(_config.max_tilt_angle);
            }
          }

          if (node["max_acc"]) {
            _config.max_acc = node["max_acc"].as<float>();
          }

          if (node["yaw_weight"]) {
            _config.yaw_weight = node["yaw_weight"].as<float>();
          }

          if (node["p_gains"]) {
            auto gains = node["p_gains"];
            if (gains.size() == 3) {
              _config.p_gains = Eigen::Vector3f{
                gains[0].as<float>(),
                gains[1].as<float>(),
                gains[2].as<float>()
              };
            }
          }

          if (node["max_rate"]) {
            _config.max_rate = node["max_rate"].as<float>();
          }

          RCLCPP_INFO(_node.get_logger(),
            "TestNeuralManual: Loaded config from: %s", config_file.c_str());
        }
      } catch (const YAML::Exception& e) {
        RCLCPP_ERROR(_node.get_logger(),
          "Failed to load config file '%s': %s. Using defaults.",
          config_file.c_str(), e.what());
      }
    }

    _config.max_tilt_angle = std::clamp(_config.max_tilt_angle, 0.1f, 1.4f);
    _config.max_acc = std::clamp(_config.max_acc, 5.0f, 30.0f);
    _config.yaw_weight = std::clamp(_config.yaw_weight, 0.0f, 1.0f);
    _config.p_gains = _config.p_gains.cwiseMax(0.1f).cwiseMin(20.0f);
    _config.max_rate = std::clamp(_config.max_rate, 0.5f, 10.0f);
  }

  Eigen::Quaternionf generateTiltSetpoint(float stick_roll, float stick_pitch) const
  {
    Eigen::Vector3f tilt_vector;
    tilt_vector.x() = stick_roll * _config.max_tilt_angle;
    tilt_vector.y() = -stick_pitch * _config.max_tilt_angle;
    tilt_vector.z() = 0.0f;

    const float tilt_magnitude = tilt_vector.norm();
    if (tilt_magnitude > _config.max_tilt_angle) {
      tilt_vector = tilt_vector / tilt_magnitude * _config.max_tilt_angle;
    }

    return axisAngleToQuaternion(tilt_vector);
  }

  float computeAccSetpoint(float stick_throttle) const
  {
    constexpr float gravity = 9.81f;
    const float acc_sp = gravity + stick_throttle * (_config.max_acc - gravity);
    return std::max(acc_sp, 0.5f);
  }

  Eigen::Vector3f computeRateSetpoint(
    const Eigen::Quaternionf& q_current,
    const Eigen::Quaternionf& q_target,
    float stick_yaw) const
  {
    using namespace px4_ros2;

    const Eigen::Vector3f z_current = extractZAxis(q_current);
    const Eigen::Vector3f z_target = extractZAxis(q_target);
    const Eigen::Quaternionf q_tilt_correction = tiltCorrectionQuaternion(z_current, z_target);
    const Eigen::Quaternionf q_reduced = q_tilt_correction * q_current;
    const Eigen::Quaternionf q_reduced_inv = q_reduced.inverse();
    const Eigen::Quaternionf q_yaw_diff = q_reduced_inv * q_target;
    const float yaw_error_angle = extractYawAngle(q_yaw_diff);
    const float weighted_yaw_error = yaw_error_angle * _config.yaw_weight;
    const float yaw_setpoint = weighted_yaw_error + stick_yaw * 1.0f;
    const Eigen::Quaternionf q_yaw_rotation = yawRotationQuaternion(yaw_setpoint);
    const Eigen::Quaternionf q_final_target = q_reduced * q_yaw_rotation;
    const Eigen::Quaternionf q_error = q_current.inverse() * q_final_target;

    Eigen::Vector3f rate_setpoint;
    rate_setpoint.x() = 2.0f * q_error.x() * _config.p_gains.x();
    rate_setpoint.y() = 2.0f * q_error.y() * _config.p_gains.y();
    rate_setpoint.z() = 2.0f * q_error.z() * _config.p_gains.z();

    if (q_error.w() < 0.0f) {
      rate_setpoint = -rate_setpoint;
    }

    rate_setpoint = rate_setpoint.cwiseMin(_config.max_rate).cwiseMax(-_config.max_rate);

    return rate_setpoint;
  }

  static Eigen::Quaternionf axisAngleToQuaternion(const Eigen::Vector3f& axis_angle)
  {
    const float angle = axis_angle.norm();

    if (angle < 1e-6f) {
      return Eigen::Quaternionf::Identity();
    }

    const Eigen::Vector3f axis = axis_angle / angle;
    return Eigen::Quaternionf(Eigen::AngleAxisf(angle, axis)).normalized();
  }

  static Eigen::Vector3f extractZAxis(const Eigen::Quaternionf& q)
  {
    const Eigen::Matrix3f R = q.toRotationMatrix();
    return R.col(2);
  }

  static Eigen::Quaternionf tiltCorrectionQuaternion(
    const Eigen::Vector3f& z_current,
    const Eigen::Vector3f& z_target)
  {
    return Eigen::Quaternionf::FromTwoVectors(z_current, z_target).normalized();
  }

  static float extractYawAngle(const Eigen::Quaternionf& q)
  {
    const float w = q.w(), x = q.x(), y = q.y(), z = q.z();
    return std::atan2(2.0f * (w*z + x*y), 1.0f - 2.0f * (y*y + z*z));
  }

  static Eigen::Quaternionf yawRotationQuaternion(float yaw_angle)
  {
    return Eigen::Quaternionf(
      Eigen::AngleAxisf(yaw_angle, Eigen::Vector3f::UnitZ())
    ).normalized();
  }
};
