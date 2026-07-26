#include <rclcpp/rclcpp.hpp>

#include <geometry_msgs/msg/transform_stamped.hpp>

#include <tf2/LinearMath/Quaternion.h>
#include <tf2_ros/transform_broadcaster.h>

#include <rm_referee_msgs/msg/robot_pos.hpp>
#include <rm_referee_msgs/msg/ground_robot_position.hpp>

namespace rm_referee {

class TfPublisher : public rclcpp::Node {
 public:
  TfPublisher(const rclcpp::NodeOptions &options) : Node("tf_publisher", options) {
    declare_parameter<std::string>("robot_pos_topic", "/rm_referee/robot_pos");
    declare_parameter<std::string>("ground_robot_position_topic", "/rm_referee/ground_robot_position");
    declare_parameter<std::string>("root_frame_id", "map");
    declare_parameter<std::string>("child_frame_prefix", "robot_");

    robot_pos_topic_ = get_parameter("robot_pos_topic").as_string();
    ground_robot_position_topic_ = get_parameter("ground_robot_position_topic").as_string();
    root_frame_id_ = get_parameter("root_frame_id").as_string();
    child_frame_prefix_ = get_parameter("child_frame_prefix").as_string();

    RCLCPP_INFO(get_logger(), "Subscribed to RobotPos topic: %s", robot_pos_topic_.c_str());
    RCLCPP_INFO(get_logger(), "Subscribed to GroundRobotPosition topic: %s", ground_robot_position_topic_.c_str());
    RCLCPP_INFO(get_logger(), "Using root frame ID: %s", root_frame_id_.c_str());
    RCLCPP_INFO(get_logger(), "Using child frame prefix: %s", child_frame_prefix_.c_str());

    tf_broadcaster_ = std::make_unique<tf2_ros::TransformBroadcaster>(*this);

    robot_pos_sub_ = create_subscription<rm_referee_msgs::msg::RobotPos>(
        robot_pos_topic_, rclcpp::SensorDataQoS(),
        std::bind(&TfPublisher::RobotPosCallback, this, std::placeholders::_1));

    ground_robot_position_sub_ = create_subscription<rm_referee_msgs::msg::GroundRobotPosition>(
        ground_robot_position_topic_, rclcpp::SensorDataQoS(),
        std::bind(&TfPublisher::GroundRobotPositionCallback, this, std::placeholders::_1));
  }

 private:
  void RobotPosCallback(const rm_referee_msgs::msg::RobotPos::SharedPtr msg) {
    geometry_msgs::msg::TransformStamped t;
    t.header.stamp = get_clock()->now();
    t.header.frame_id = root_frame_id_;
    t.child_frame_id = child_frame_prefix_ + "self";

    t.transform.translation.x = msg->x;
    t.transform.translation.y = msg->y;
    t.transform.translation.z = 0.0;

    tf2::Quaternion q;
    q.setRPY(0, 0, msg->angle * M_PI / 180.0);  // Convert degrees to radians
    t.transform.rotation.x = q.x();
    t.transform.rotation.y = q.y();
    t.transform.rotation.z = q.z();
    t.transform.rotation.w = q.w();

    tf_broadcaster_->sendTransform(t);
  }

  void GroundRobotPositionCallback(const rm_referee_msgs::msg::GroundRobotPosition::SharedPtr msg) {
    const auto now = get_clock()->now();
    PublishTF(now, "hero", msg->hero_x, msg->hero_y);
    PublishTF(now, "engineer", msg->engineer_x, msg->engineer_y);
    PublishTF(now, "standard_3", msg->standard_3_x, msg->standard_3_y);
    PublishTF(now, "standard_4", msg->standard_4_x, msg->standard_4_y);
  }

  void PublishTF(const rclcpp::Time &time, const std::string &robot_name, float x, float y) {
    geometry_msgs::msg::TransformStamped t;
    t.header.stamp = time;
    t.header.frame_id = root_frame_id_;
    t.child_frame_id = child_frame_prefix_ + robot_name;

    t.transform.translation.x = x;
    t.transform.translation.y = y;
    t.transform.translation.z = 0.0;

    t.transform.rotation.x = 0.0;
    t.transform.rotation.y = 0.0;
    t.transform.rotation.z = 0.0;
    t.transform.rotation.w = 1.0;

    tf_broadcaster_->sendTransform(t);
  }

  std::string robot_pos_topic_{};
  std::string ground_robot_position_topic_{};
  std::string root_frame_id_{};
  std::string child_frame_prefix_{};

  std::unique_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_;
  rclcpp::Subscription<rm_referee_msgs::msg::RobotPos>::SharedPtr robot_pos_sub_;
  rclcpp::Subscription<rm_referee_msgs::msg::GroundRobotPosition>::SharedPtr ground_robot_position_sub_;
};

}  // namespace rm_referee

#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(rm_referee::TfPublisher)
