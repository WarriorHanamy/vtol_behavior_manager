/****************************************************************************
 * Copyright (c) 2025 PX4 Development Team.
 * SPDX-License-Identifier: BSD-3-Clause
 ****************************************************************************/
/**
 * @file test_neural_manual_mode.hpp
 * @brief Manual flight mode with RC control
 * @author steven cheng
 * @date created on 2025.03.20
 */

#pragma once

#include <Eigen/Core>
#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/experimental/acc_rates.hpp>
#include <px4_ros2/odometry/attitude.hpp>
#include <rclcpp/rclcpp.hpp>
#include <yaml-cpp/yaml.h>

/**
 * @class TestNeuralManualMode
 * @brief Manual flight mode with RC control
 *
 * This mode converts RC stick inputs into acceleration and rate setpoints.
 * Deactivation is handled externally by the executor.
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
 */
class TestNeuralManualMode : public px4_ros2::ModeBase {
public:
  explicit TestNeuralManualMode(rclcpp::Node &node)
      : ModeBase(node, Settings{"TestNeuralManual"}) {
    loadConfigFromYaml();

    _manual_control_input =
        std::make_shared<px4_ros2::ManualControlInput>(*this);
    _attitude = std::make_shared<px4_ros2::OdometryAttitude>(*this);
    _acc_rates_setpoint =
        std::make_shared<px4_ros2::AccRatesSetpointType>(*this);

    RCLCPP_INFO(_node.get_logger(),
                "TestNeuralManualMode initialized: max_tilt=%.1f deg, "
                "max_acc=%.1f m/s^2, max_yaw_rate=%.1f rad/s, throttle_deadzone=%.2f",
                px4_ros2::radToDeg(_config.max_tilt_angle), _config.max_acc,
                _config.max_yaw_rate, _config.throttle_deadzone);
  }

  ~TestNeuralManualMode() override = default;

  TestNeuralManualMode(const TestNeuralManualMode &) = delete;
  TestNeuralManualMode &operator=(const TestNeuralManualMode &) = delete;
  TestNeuralManualMode(TestNeuralManualMode &&) noexcept = default;
  TestNeuralManualMode &operator=(TestNeuralManualMode &&) noexcept = default;

protected:
  void onActivate() override {
    RCLCPP_INFO(_node.get_logger(), "TestNeuralManualMode activated");
  }

  void onDeactivate() override {
    RCLCPP_INFO(_node.get_logger(), "TestNeuralManualMode deactivated");
  }

  void updateSetpoint(float dt_s) override {
    if (!_manual_control_input->isValid()) {
      RCLCPP_WARN_THROTTLE(
          _node.get_logger(), *_node.get_clock(), 1000,
          "TestNeuralManual: Waiting for valid manual control input...");
      return;
    }

    if (!_attitude->lastValid()) {
      RCLCPP_WARN_THROTTLE(_node.get_logger(), *_node.get_clock(), 1000,
                           "TestNeuralManual: Waiting for attitude data...");
      return;
    }

    const float stick_roll = _manual_control_input->roll();
    const float stick_pitch = _manual_control_input->pitch();
    const float stick_yaw = _manual_control_input->yaw();
    const float stick_throttle = _manual_control_input->throttle();

    const Eigen::Quaternionf q_current = _attitude->attitude();
    const Eigen::Quaternionf q_tilt =
        generateTiltSetpoint(stick_roll, stick_pitch);
    const float acc_sp = computeAccSetpoint(stick_throttle);
    const Eigen::Vector3f rates_sp =
        computeRateSetpoint(q_current, q_tilt, stick_yaw);

    _acc_rates_setpoint->update(acc_sp, rates_sp);

    RCLCPP_DEBUG_THROTTLE(_node.get_logger(), *_node.get_clock(), 500,
                          "TestNeuralManual: sticks[%.2f,%.2f,%.2f,%.2f] -> "
                          "acc=%.2f, rates[%.2f,%.2f,%.2f]",
                          stick_roll, stick_pitch, stick_yaw, stick_throttle,
                          acc_sp, rates_sp[0], rates_sp[1], rates_sp[2]);
  }

private:
  struct Config {
    float max_tilt_angle{0.785f};
    float max_acc{12.0f};
    Eigen::Vector3f p_gains{5.0f, 5.0f, 3.0f};
    float max_rate{3.0f};
    float max_yaw_rate{1.0f};
    float throttle_deadzone{0.1f};
  };

  std::shared_ptr<px4_ros2::ManualControlInput> _manual_control_input;
  std::shared_ptr<px4_ros2::OdometryAttitude> _attitude;
  std::shared_ptr<px4_ros2::AccRatesSetpointType> _acc_rates_setpoint;
  Config _config;

  void loadConfigFromYaml() {
    _config = Config{};

    std::string config_file;
    if (_node.get_parameter("config_file", config_file) &&
        !config_file.empty()) {
      try {
        YAML::Node config = YAML::LoadFile(config_file);

        if (config["neural_manual"]) {
          auto node = config["neural_manual"];

          if (node["max_tilt_angle"]) {
            _config.max_tilt_angle = node["max_tilt_angle"].as<float>();
            if (_config.max_tilt_angle > 2.0f) {
              _config.max_tilt_angle =
                  px4_ros2::degToRad(_config.max_tilt_angle);
            }
          }

          if (node["max_acc"]) {
            _config.max_acc = node["max_acc"].as<float>();
          }

          if (node["p_gains"]) {
            auto gains = node["p_gains"];
            if (gains.size() == 3) {
              _config.p_gains =
                  Eigen::Vector3f{gains[0].as<float>(), gains[1].as<float>(),
                                  gains[2].as<float>()};
            }
          }

          if (node["max_rate"]) {
            _config.max_rate = node["max_rate"].as<float>();
          }

          if (node["max_yaw_rate"]) {
            _config.max_yaw_rate = node["max_yaw_rate"].as<float>();
          }

          if (node["throttle_deadzone"]) {
            _config.throttle_deadzone = node["throttle_deadzone"].as<float>();
          }

          RCLCPP_INFO(_node.get_logger(),
                      "TestNeuralManual: Loaded config from: %s",
                      config_file.c_str());
        }
      } catch (const YAML::Exception &e) {
        RCLCPP_ERROR(_node.get_logger(),
                     "Failed to load config file '%s': %s. Using defaults.",
                     config_file.c_str(), e.what());
      }
    }

    _config.max_tilt_angle = std::clamp(_config.max_tilt_angle, 0.1f, 1.4f);
    _config.max_acc = std::clamp(_config.max_acc, 5.0f, 30.0f);
    _config.p_gains = _config.p_gains.cwiseMax(0.1f).cwiseMin(20.0f);
    _config.max_rate = std::clamp(_config.max_rate, 0.5f, 10.0f);
    _config.max_yaw_rate = std::clamp(_config.max_yaw_rate, 0.1f, 5.0f);
    _config.throttle_deadzone = std::clamp(_config.throttle_deadzone, 0.0f, 0.3f);
  }

  Eigen::Quaternionf generateTiltSetpoint(float stick_roll,
                                          float stick_pitch) const {
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

  float computeAccSetpoint(float stick_throttle) const {
    constexpr float gravity = 9.81f;
    float throttle = stick_throttle;
    if (std::abs(throttle) < _config.throttle_deadzone) {
      throttle = 0.0f;
    } else {
      throttle = throttle - std::copysign(_config.throttle_deadzone, throttle);
      throttle /= (1.0f - _config.throttle_deadzone);
    }
    const float acc_sp = gravity + throttle * (_config.max_acc - gravity);
    return std::min(-acc_sp, 0.0f);
  }

  Eigen::Vector3f computeRateSetpoint(const Eigen::Quaternionf &q_current,
                                      const Eigen::Quaternionf &q_target,
                                      float stick_yaw) const {
    const Eigen::Vector3f z_current = extractZAxis(q_current);
    const Eigen::Vector3f z_target = extractZAxis(q_target);
    const Eigen::Quaternionf q_tilt_correction =
        tiltCorrectionQuaternion(z_current, z_target);
    const Eigen::Quaternionf q_error = q_current.inverse() * (q_tilt_correction * q_current);

    Eigen::Vector3f rate_setpoint;
    rate_setpoint.x() = 2.0f * q_error.x() * _config.p_gains.x();
    rate_setpoint.y() = 2.0f * q_error.y() * _config.p_gains.y();
    rate_setpoint.z() = stick_yaw * _config.max_yaw_rate;

    if (q_error.w() < 0.0f) {
      rate_setpoint.x() = -rate_setpoint.x();
      rate_setpoint.y() = -rate_setpoint.y();
    }

    rate_setpoint.x() = std::clamp(rate_setpoint.x(), -_config.max_rate, _config.max_rate);
    rate_setpoint.y() = std::clamp(rate_setpoint.y(), -_config.max_rate, _config.max_rate);
    rate_setpoint.z() = std::clamp(rate_setpoint.z(), -_config.max_yaw_rate, _config.max_yaw_rate);

    return rate_setpoint;
  }

  static Eigen::Quaternionf
  axisAngleToQuaternion(const Eigen::Vector3f &axis_angle) {
    const float angle = axis_angle.norm();

    if (angle < 1e-6f) {
      return Eigen::Quaternionf::Identity();
    }

    const Eigen::Vector3f axis = axis_angle / angle;
    return Eigen::Quaternionf(Eigen::AngleAxisf(angle, axis)).normalized();
  }

  static Eigen::Vector3f extractZAxis(const Eigen::Quaternionf &q) {
    const Eigen::Matrix3f R = q.toRotationMatrix();
    return R.col(2);
  }

  static Eigen::Quaternionf
  tiltCorrectionQuaternion(const Eigen::Vector3f &z_current,
                           const Eigen::Vector3f &z_target) {
    return Eigen::Quaternionf::FromTwoVectors(z_current, z_target).normalized();
  }
};
