#pragma once

#include <rclcpp/rclcpp.hpp>
#include <px4_msgs/msg/mavlink_log.hpp>
#include <px4_ros2/utils/message_version.hpp>
#include <string>
#include <cstring>

namespace neural_executor
{

enum class LogSeverity : uint8_t {
  Emergency = 0,
  Alert = 1,
  Critical = 2,
  Error = 3,
  Warning = 4,
  Notice = 5,
  Info = 6,
  Debug = 7
};

class MavlinkLogger
{
public:
  explicit MavlinkLogger(rclcpp::Node & node)
  : _node(node)
  {
    _publisher = _node.create_publisher<px4_msgs::msg::MavlinkLog>(
      "fmu/in/mavlink_log" + px4_ros2::getMessageNameVersion<px4_msgs::msg::MavlinkLog>(),
      rclcpp::QoS(10));
  }

  void log(const std::string & text, LogSeverity severity)
  {
    px4_msgs::msg::MavlinkLog msg{};
    msg.timestamp = _node.get_clock()->now().nanoseconds() / 1000;
    size_t copy_len = std::min(text.size(), sizeof(msg.text) - 1);
    std::memcpy(msg.text.data(), text.c_str(), copy_len);
    msg.text[copy_len] = '\0';
    msg.severity = static_cast<uint8_t>(severity);
    _publisher->publish(msg);
  }

  void emergency(const std::string & text) { log(text, LogSeverity::Emergency); }
  void alert(const std::string & text) { log(text, LogSeverity::Alert); }
  void critical(const std::string & text) { log(text, LogSeverity::Critical); }
  void error(const std::string & text) { log(text, LogSeverity::Error); }
  void warning(const std::string & text) { log(text, LogSeverity::Warning); }
  void notice(const std::string & text) { log(text, LogSeverity::Notice); }
  void info(const std::string & text) { log(text, LogSeverity::Info); }
  void debug(const std::string & text) { log(text, LogSeverity::Debug); }

private:
  rclcpp::Node & _node;
  rclcpp::Publisher<px4_msgs::msg::MavlinkLog>::SharedPtr _publisher;
};

} // namespace neural_executor
