
#pragma once

#include <rclcpp/rclcpp.hpp>

#include <librm.hpp>

#include <rm_referee_msgs/msg/custom_robot_data.hpp>
#include <rm_referee_msgs/msg/robot_custom_data.hpp>
#include <rm_referee_msgs/msg/robot_custom_data2.hpp>
#include <rm_referee_msgs/msg/custom_control.hpp>
#include <rm_referee_msgs/msg/buff.hpp>
#include <rm_referee_msgs/msg/dart_client_cmd.hpp>
#include <rm_referee_msgs/msg/dart_info.hpp>
#include <rm_referee_msgs/msg/event_data.hpp>
#include <rm_referee_msgs/msg/game_result.hpp>
#include <rm_referee_msgs/msg/game_robot_hp.hpp>
#include <rm_referee_msgs/msg/game_status.hpp>
#include <rm_referee_msgs/msg/ground_robot_position.hpp>
#include <rm_referee_msgs/msg/hurt_data.hpp>
#include <rm_referee_msgs/msg/power_heat_data.hpp>
#include <rm_referee_msgs/msg/projectile_allowance.hpp>
#include <rm_referee_msgs/msg/radar_info.hpp>
#include <rm_referee_msgs/msg/radar_mark_data.hpp>
#include <rm_referee_msgs/msg/referee_warning.hpp>
#include <rm_referee_msgs/msg/rfid_status.hpp>
#include <rm_referee_msgs/msg/robot_pos.hpp>
#include <rm_referee_msgs/msg/robot_status.hpp>
#include <rm_referee_msgs/msg/sentry_info.hpp>
#include <rm_referee_msgs/msg/shoot_data.hpp>
#include <rm_referee_msgs/msg/map_command.hpp>
#include <rm_referee_msgs/srv/tx.hpp>

#include "referee_node/asio_serial.hpp"
#include "referee_node/byte_stream_recorder.hpp"

class RefereeNode : public rclcpp::Node {
 public:
  explicit RefereeNode(const rclcpp::NodeOptions& options = rclcpp::NodeOptions()
                                                                .allow_undeclared_parameters(true)
                                                                .automatically_declare_parameters_from_overrides(true));
  ~RefereeNode() override;

 protected:
  RefereeNode(const std::string& node_name, const rclcpp::NodeOptions& options, bool start_serial_io);
  void FeedNormalData(const std::string& data);
  void FeedVtData(const std::string& data);

 private:
  void SpawnPublishers();
  void GetParameters();
  void SerialInit(std::string tty_device, std::unique_ptr<asio_serial::Serial>& serial, size_t baudrate = 115200);
  template <rm::device::RefereeRevision revision>
  void PublishMsg(uint16_t cmd_id, const rm::device::RefereeProtocol<revision>& referee_data);

 private:
  /** <Normal members> **/
  std::unique_ptr<asio_serial::Serial> normal_serial_{nullptr};
  std::unique_ptr<asio_serial::Serial> vt_serial_{nullptr};
  /** </Normal members> **/

 private:
  /** <Parameters> **/
  std::string param_normal_tty_device_{};
  std::string param_vt_tty_device_{};
  bool param_new_vt_{};
  bool param_enable_normal_{};
  bool param_enable_vt_{};
  bool param_record_raw_data_{};
  std::string param_raw_data_path_{};
  /** </Parameters> **/

 private:
  /** <Threads> **/
  std::thread normal_serial_rx_thread_;
  std::thread vt_serial_rx_thread_;
  std::atomic<bool> stop_threads_{false};
  /** </Threads> **/
  /** <Raw Data Recording> **/
  std::unique_ptr<referee_node::ByteStreamRecorder> normal_recorder_;
  std::unique_ptr<referee_node::ByteStreamRecorder> vt_recorder_;
  /** </Raw Data Recording> **/
  /** <Decoders> **/
  rm::device::Referee<rm::device::RefereeRevision::kNewV200> normal_referee_;
  rm::device::Referee<rm::device::RefereeRevision::kNewV200> vt_referee_;
  /** </Decoders> **/

 private:
  /** <Publishers> **/
  rclcpp::Publisher<rm_referee_msgs::msg::GameStatus>::SharedPtr game_status_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::GameResult>::SharedPtr game_result_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::GameRobotHP>::SharedPtr game_robot_hp_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::EventData>::SharedPtr event_data_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::RefereeWarning>::SharedPtr referee_warning_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::DartInfo>::SharedPtr dart_info_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::RobotStatus>::SharedPtr robot_status_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::PowerHeatData>::SharedPtr power_heat_data_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::RobotPos>::SharedPtr robot_pos_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::Buff>::SharedPtr buff_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::HurtData>::SharedPtr hurt_data_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::ShootData>::SharedPtr shoot_data_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::ProjectileAllowance>::SharedPtr projectile_allowance_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::RFIDStatus>::SharedPtr rfid_status_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::DartClientCmd>::SharedPtr dart_client_cmd_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::GroundRobotPosition>::SharedPtr ground_robot_position_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::RadarMarkData>::SharedPtr radar_mark_data_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::SentryInfo>::SharedPtr sentry_info_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::RadarInfo>::SharedPtr radar_info_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::CustomRobotData>::SharedPtr custom_robot_data_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::RobotCustomData>::SharedPtr robot_custom_data_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::RobotCustomData2>::SharedPtr robot_custom_data_2_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::CustomControl>::SharedPtr custom_control_pub_{nullptr};
  rclcpp::Publisher<rm_referee_msgs::msg::MapCommand>::SharedPtr map_command_pub_{nullptr};
  /** </Publishers> **/

  /** <msgs> **/
  rm_referee_msgs::msg::GameStatus game_status_msg_{};
  rm_referee_msgs::msg::GameResult game_result_msg_{};
  rm_referee_msgs::msg::GameRobotHP game_robot_hp_msg_{};
  rm_referee_msgs::msg::EventData event_data_msg_{};
  rm_referee_msgs::msg::RefereeWarning referee_warning_msg_{};
  rm_referee_msgs::msg::DartInfo dart_info_msg_{};
  rm_referee_msgs::msg::RobotStatus robot_status_msg_{};
  rm_referee_msgs::msg::PowerHeatData power_heat_data_msg_{};
  rm_referee_msgs::msg::RobotPos robot_pos_msg_{};
  rm_referee_msgs::msg::Buff buff_msg_{};
  rm_referee_msgs::msg::HurtData hurt_data_msg_{};
  rm_referee_msgs::msg::ShootData shoot_data_msg_{};
  rm_referee_msgs::msg::ProjectileAllowance projectile_allowance_msg_{};
  rm_referee_msgs::msg::RFIDStatus rfid_status_msg_{};
  rm_referee_msgs::msg::DartClientCmd dart_client_cmd_msg_{};
  rm_referee_msgs::msg::GroundRobotPosition ground_robot_position_msg_{};
  rm_referee_msgs::msg::RadarMarkData radar_mark_data_msg_{};
  rm_referee_msgs::msg::SentryInfo sentry_info_msg_{};
  rm_referee_msgs::msg::RadarInfo radar_info_msg_{};
  rm_referee_msgs::msg::CustomRobotData custom_robot_data_msg_{};
  rm_referee_msgs::msg::RobotCustomData robot_custom_data_msg_{};
  rm_referee_msgs::msg::RobotCustomData2 robot_custom_data_2_msg_{};
  rm_referee_msgs::msg::CustomControl custom_control_msg_{};
  rm_referee_msgs::msg::MapCommand map_command_msg_{};
  /** </msgs> **/

 private:
  rclcpp::Service<rm_referee_msgs::srv::Tx>::SharedPtr referee_srv_{nullptr};
};
