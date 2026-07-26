
#include "referee_node/referee_node.hpp"
#include "referee_node/log_utils.hpp"

RefereeNode::RefereeNode(const rclcpp::NodeOptions &options) : RefereeNode("referee_node", options, true) {}

RefereeNode::RefereeNode(const std::string &node_name, const rclcpp::NodeOptions &options, bool start_serial_io)
    : rclcpp::Node(node_name, options) {
  SpawnPublishers();
  if (start_serial_io) {
    GetParameters();
  }

  // 为两个 Referee 对象注册回调函数
  normal_referee_.AttachCallback([this](uint16_t cmd_id, uint8_t seq) { PublishMsg(cmd_id, normal_referee_.data()); });
  vt_referee_.AttachCallback([this](uint16_t cmd_id, uint8_t seq) { PublishMsg(cmd_id, vt_referee_.data()); });

  if (!start_serial_io) {
    return;
  }

  // 初始化串口、启动线程
  if (param_enable_normal_) {
    RCLCPP_INFO(get_logger(), ("Normal data link: " + text::Green("Enabled") + " @ %s").c_str(),
                param_normal_tty_device_.c_str());
    SerialInit(param_normal_tty_device_, normal_serial_);

    // 启用原始数据记录，创建一个Recorder
    if (param_record_raw_data_) {
      const auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
      std::stringstream ss;
      ss << param_raw_data_path_ << "/normal_raw_data_" << std::put_time(std::localtime(&now), "%Y%m%d_%H%M%S")
         << ".bin";
      normal_recorder_ = std::make_unique<referee_node::ByteStreamRecorder>(ss.str());
      if (normal_recorder_->IsOpen()) {
        RCLCPP_INFO(get_logger(), "Recording normal raw data to: %s", ss.str().c_str());
      } else {
        RCLCPP_ERROR(get_logger(), "Failed to open file for recording normal raw data: %s", ss.str().c_str());
        normal_recorder_.reset();
      }
    }

    normal_serial_rx_thread_ = std::thread([this] {
      while (!stop_threads_) {
        const auto data = normal_serial_->read();
        // 记录原始数据
        if (normal_recorder_) {
          normal_recorder_->Write(data);
        }
        FeedNormalData(data);
      }
    });
  } else {
    RCLCPP_INFO(get_logger(), "%s", ("Normal data link: " + text::Red("Disabled")).c_str());
  }
  if (param_enable_vt_) {
    RCLCPP_INFO(get_logger(), ("VT data link: " + text::Green("Enabled") + " @ %s").c_str(),
                param_vt_tty_device_.c_str());
    if (param_new_vt_) {
      SerialInit(param_vt_tty_device_, vt_serial_, 921600);
    } else {
      SerialInit(param_vt_tty_device_, vt_serial_);
    }

    // 启用原始数据记录，创建一个Recorder
    if (param_record_raw_data_) {
      auto now = std::chrono::system_clock::now();
      auto now_time_t = std::chrono::system_clock::to_time_t(now);
      std::stringstream ss;
      ss << param_raw_data_path_ << "/vt_raw_data_" << std::put_time(std::localtime(&now_time_t), "%Y%m%d_%H%M%S")
         << ".bin";
      vt_recorder_ = std::make_unique<referee_node::ByteStreamRecorder>(ss.str());
      if (vt_recorder_->IsOpen()) {
        RCLCPP_INFO(get_logger(), "Recording VT raw data to: %s", ss.str().c_str());
      } else {
        RCLCPP_ERROR(get_logger(), "Failed to open file for recording VT raw data: %s", ss.str().c_str());
        vt_recorder_.reset();
      }
    }

    vt_serial_rx_thread_ = std::thread([this] {
      while (!stop_threads_) {
        const auto data = vt_serial_->read();
        // 记录原始数据
        if (vt_recorder_) {
          vt_recorder_->Write(data);
        }
        FeedVtData(data);
      }
    });
  } else {
    RCLCPP_INFO(get_logger(), "%s", ("VT data link: " + text::Red("Disabled")).c_str());
  }

  if (!param_enable_normal_ && !param_enable_vt_) {
    RCLCPP_ERROR(get_logger(), "Both normal and VT data links are disabled, exiting...");
    rclcpp::shutdown();
  }

  if (param_enable_normal_) {
    // 如果启用了常规链路，就创建裁判系统服务
    referee_srv_ = create_service<rm_referee_msgs::srv::Tx>(
        "/rm_referee/tx", [this](const std::shared_ptr<rm_referee_msgs::srv::Tx::Request> request,
                                 std::shared_ptr<rm_referee_msgs::srv::Tx::Response> response) {
          if (normal_serial_->write(std::string(request->data.begin(), request->data.end())) == request->data.size()) {
            response->ok = true;
          } else {
            response->ok = false;
          }
          response->header.stamp = get_clock()->now();
        });
    RCLCPP_INFO(get_logger(), "Referee service is now at /rm_referee/tx");
  }
}

void RefereeNode::FeedNormalData(const std::string &data) {
  for (auto byte : data) {
    normal_referee_ << byte;
  }
  if (normal_referee_.loss_rate() > 10.f) {
    RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000,
                         text::Yellow("High loss rate on normal link! %.2f%%").c_str(), normal_referee_.loss_rate());
  }
}

void RefereeNode::FeedVtData(const std::string &data) {
  for (auto byte : data) {
    vt_referee_ << byte;
  }
  if (vt_referee_.loss_rate() > 10.f) {
    RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 2000,
                         text::Yellow("High loss rate on VT link! %.2f%%").c_str(), vt_referee_.loss_rate());
  }
}

RefereeNode::~RefereeNode() {
  // 设置停止标志
  stop_threads_ = true;

  // 关闭串口以中断阻塞的读操作
  if (param_enable_normal_) {
    normal_serial_->close();
  }
  if (param_enable_vt_) {
    vt_serial_->close();
  }

  // 等待线程结束
  if (normal_serial_rx_thread_.joinable()) {
    normal_serial_rx_thread_.join();
  }
  if (vt_serial_rx_thread_.joinable()) {
    vt_serial_rx_thread_.join();
  }

  // 记录器会在析构时自动关闭文件
  if (normal_recorder_) {
    RCLCPP_INFO(get_logger(), "Normal raw data file closed");
  }
  if (vt_recorder_) {
    RCLCPP_INFO(get_logger(), "VT raw data file closed");
  }
}

void RefereeNode::SpawnPublishers() {
  game_status_pub_ = create_publisher<rm_referee_msgs::msg::GameStatus>(     //
      "/rm_referee/game_status",                                             //
      rclcpp::SensorDataQoS());                                              //
  game_result_pub_ = create_publisher<rm_referee_msgs::msg::GameResult>(     //
      "/rm_referee/game_result",                                             //
      rclcpp::SensorDataQoS());                                              //
  game_robot_hp_pub_ = create_publisher<rm_referee_msgs::msg::GameRobotHP>(  //
      "/rm_referee/game_robot_hp",                                           //
      rclcpp::SensorDataQoS());
  event_data_pub_ = create_publisher<rm_referee_msgs::msg::EventData>(  //
      "/rm_referee/event_data",                                         //
      rclcpp::SensorDataQoS());
  referee_warning_pub_ = create_publisher<rm_referee_msgs::msg::RefereeWarning>(  //
      "/rm_referee/referee_warning",                                              //
      rclcpp::SensorDataQoS());
  dart_info_pub_ = create_publisher<rm_referee_msgs::msg::DartInfo>(  //
      "/rm_referee/dart_info",                                        //
      rclcpp::SensorDataQoS());
  robot_status_pub_ = create_publisher<rm_referee_msgs::msg::RobotStatus>(  //
      "/rm_referee/robot_status",                                           //
      rclcpp::SensorDataQoS());
  power_heat_data_pub_ = create_publisher<rm_referee_msgs::msg::PowerHeatData>(  //
      "/rm_referee/power_heat_data",                                             //
      rclcpp::SensorDataQoS());
  robot_pos_pub_ = create_publisher<rm_referee_msgs::msg::RobotPos>(  //
      "/rm_referee/robot_pos",                                        //
      rclcpp::SensorDataQoS());
  buff_pub_ = create_publisher<rm_referee_msgs::msg::Buff>(  //
      "/rm_referee/buff",                                    //
      rclcpp::SensorDataQoS());
  hurt_data_pub_ = create_publisher<rm_referee_msgs::msg::HurtData>(  //
      "/rm_referee/hurt_data",                                        //
      rclcpp::SensorDataQoS());
  shoot_data_pub_ = create_publisher<rm_referee_msgs::msg::ShootData>(  //
      "/rm_referee/shoot_data",                                         //
      rclcpp::SensorDataQoS());
  projectile_allowance_pub_ = create_publisher<rm_referee_msgs::msg::ProjectileAllowance>(  //
      "/rm_referee/projectile_allowance",                                                   //
      rclcpp::SensorDataQoS());
  rfid_status_pub_ = create_publisher<rm_referee_msgs::msg::RFIDStatus>(  //
      "/rm_referee/rfid_status",                                          //
      rclcpp::SensorDataQoS());
  dart_client_cmd_pub_ = create_publisher<rm_referee_msgs::msg::DartClientCmd>(  //
      "/rm_referee/dart_client_cmd",                                             //
      rclcpp::SensorDataQoS());
  ground_robot_position_pub_ = create_publisher<rm_referee_msgs::msg::GroundRobotPosition>(  //
      "/rm_referee/ground_robot_position",                                                   //
      rclcpp::SensorDataQoS());
  radar_mark_data_pub_ = create_publisher<rm_referee_msgs::msg::RadarMarkData>(  //
      "/rm_referee/radar_mark_data",                                             //
      rclcpp::SensorDataQoS());
  sentry_info_pub_ = create_publisher<rm_referee_msgs::msg::SentryInfo>(  //
      "/rm_referee/sentry_info",                                          //
      rclcpp::SensorDataQoS());
  radar_info_pub_ = create_publisher<rm_referee_msgs::msg::RadarInfo>(  //
      "/rm_referee/radar_info",                                         //
      rclcpp::SensorDataQoS());
  custom_robot_data_pub_ = create_publisher<rm_referee_msgs::msg::CustomRobotData>(  //
      "/rm_referee/custom_robot_data",                                               //
      rclcpp::SensorDataQoS());
  robot_custom_data_pub_ = create_publisher<rm_referee_msgs::msg::RobotCustomData>(  //
      "/rm_referee/robot_custom_data",                                               //
      rclcpp::SensorDataQoS());
  robot_custom_data_2_pub_ = create_publisher<rm_referee_msgs::msg::RobotCustomData2>(  //
      "/rm_referee/robot_custom_data_2",                                                //
      rclcpp::SensorDataQoS());
  custom_control_pub_ = create_publisher<rm_referee_msgs::msg::CustomControl>(  //
      "/rm_referee/custom_control",                                               //
      rclcpp::SensorDataQoS());
  map_command_pub_ = create_publisher<rm_referee_msgs::msg::MapCommand>(  //
      "/rm_referee/map_command",                                          //
      rclcpp::SensorDataQoS());
  RCLCPP_INFO(get_logger(), "Publishers spawned");
}

void RefereeNode::GetParameters() {
  param_enable_normal_ = declare_parameter("enable_normal", false);
  param_enable_vt_ = declare_parameter("enable_vt", false);
  param_new_vt_ = declare_parameter("new_vt", false);
  param_normal_tty_device_ = declare_parameter("normal_tty_device", "/dev/ttyUSB0");
  param_vt_tty_device_ = declare_parameter("vt_tty_device", "/dev/ttyUSB0");
  param_record_raw_data_ = declare_parameter("record_raw_data", false);
  param_raw_data_path_ = declare_parameter("raw_data_path", "/tmp/rm_referee_data");
}

/**
 * @brief 初始化串口
 * @param tty_device 串口设备名
 * @param serial     Serial对象指针
 */
void RefereeNode::SerialInit(std::string tty_device, std::unique_ptr<asio_serial::Serial> &serial, size_t baudrate) {
  serial = std::make_unique<asio_serial::Serial>(tty_device, baudrate, 1000);
  if (!serial->isOpen()) {
    RCLCPP_ERROR(get_logger(), "Failed to open normal serial port: %s", tty_device.c_str());
    rclcpp::shutdown();
  }
  RCLCPP_INFO(get_logger(), "Serial port %s is open", tty_device.c_str());
}

/**
 * @brief 解包完成的回调函数，把消息发布出去
 * @param cmd_id  命令码
 * @param referee_data 裁判系统数据对象
 */
template <rm::device::RefereeRevision revision>
void RefereeNode::PublishMsg(uint16_t cmd_id, const rm::device::RefereeProtocol<revision> &referee_data) {
  RCLCPP_DEBUG(get_logger(), "Received a packet with cmd_id: 0x%04x", cmd_id);

  switch (cmd_id) {
    using CmdEnum = rm::device::RefereeCmdId<revision>;
    case CmdEnum::kGameStatus: {
      game_status_msg_.header.stamp = get_clock()->now();
      game_status_msg_.game_type = referee_data.game_status.game_type;
      game_status_msg_.game_progress = referee_data.game_status.game_progress;
      game_status_msg_.stage_remain_time = referee_data.game_status.stage_remain_time;
      game_status_msg_.sync_timestamp = referee_data.game_status.SyncTimeStamp;
      game_status_pub_->publish(game_status_msg_);
      break;
    }
    case CmdEnum::kGameResult: {
      game_result_msg_.header.stamp = get_clock()->now();
      game_result_msg_.winner = referee_data.game_result.winner;
      game_result_pub_->publish(game_result_msg_);
      break;
    }
    case CmdEnum::kGameRobotHp: {
      game_robot_hp_msg_.header.stamp = get_clock()->now();
      game_robot_hp_msg_.ally_1_robot_hp = referee_data.game_robot_HP.ally_1_robot_HP;
      game_robot_hp_msg_.ally_2_robot_hp = referee_data.game_robot_HP.ally_2_robot_HP;
      game_robot_hp_msg_.ally_3_robot_hp = referee_data.game_robot_HP.ally_3_robot_HP;
      game_robot_hp_msg_.ally_4_robot_hp = referee_data.game_robot_HP.ally_4_robot_HP;
      game_robot_hp_msg_.damage_difference = referee_data.game_robot_HP.damage_difference;
      game_robot_hp_msg_.ally_7_robot_hp = referee_data.game_robot_HP.ally_7_robot_HP;
      game_robot_hp_msg_.ally_outpost_hp = referee_data.game_robot_HP.ally_outpost_HP;
      game_robot_hp_msg_.ally_base_hp = referee_data.game_robot_HP.ally_base_HP;
      game_robot_hp_msg_.enemy_outpost_hp = referee_data.game_robot_HP.enemy_outpost_HP;
      game_robot_hp_msg_.enemy_base_hp = referee_data.game_robot_HP.enemy_base_HP;
      game_robot_hp_pub_->publish(game_robot_hp_msg_);
      break;
    }
    case CmdEnum::kEventData: {
      event_data_msg_.header.stamp = get_clock()->now();
      event_data_msg_.event_data = referee_data.event_data.event_data;
      event_data_pub_->publish(event_data_msg_);
      break;
    }
    case CmdEnum::kRefereeWarning: {
      referee_warning_msg_.header.stamp = get_clock()->now();
      referee_warning_msg_.level = referee_data.referee_warning.level;
      referee_warning_msg_.offending_robot_id = referee_data.referee_warning.offending_robot_id;
      referee_warning_msg_.count = referee_data.referee_warning.count;
      referee_warning_pub_->publish(referee_warning_msg_);
      break;
    }
    case CmdEnum::kDartInformation: {
      dart_info_msg_.header.stamp = get_clock()->now();
      dart_info_msg_.dart_remaining_time = referee_data.dart_info.dart_remaining_time;
      dart_info_msg_.dart_info = referee_data.dart_info.dart_info;
      dart_info_pub_->publish(dart_info_msg_);
      break;
    }
    case CmdEnum::kRobotStatus: {
      robot_status_msg_.header.stamp = get_clock()->now();
      robot_status_msg_.robot_id = referee_data.robot_status.robot_id;
      robot_status_msg_.robot_level = referee_data.robot_status.robot_level;
      robot_status_msg_.current_hp = referee_data.robot_status.current_HP;
      robot_status_msg_.maximum_hp = referee_data.robot_status.maximum_HP;
      robot_status_msg_.shooter_barrel_cooling_value = referee_data.robot_status.shooter_barrel_cooling_value;
      robot_status_msg_.shooter_barrel_heat_limit = referee_data.robot_status.shooter_barrel_heat_limit;
      robot_status_msg_.chassis_power_limit = referee_data.robot_status.chassis_power_limit;
      robot_status_msg_.bullet_speed_limit = referee_data.robot_status.bullet_speed_limit;
      robot_status_msg_.power_management_gimbal_output = referee_data.robot_status.power_management_gimbal_output;
      robot_status_msg_.power_management_chassis_output = referee_data.robot_status.power_management_chassis_output;
      robot_status_msg_.power_management_shooter_output = referee_data.robot_status.power_management_shooter_output;
      robot_status_pub_->publish(robot_status_msg_);
      break;
    }
    case CmdEnum::kPowerHeatData: {
      power_heat_data_msg_.header.stamp = get_clock()->now();
      power_heat_data_msg_.reserved = referee_data.power_heat_data.reserved;
      power_heat_data_msg_.reserved_2 = referee_data.power_heat_data.reserved_2;
      power_heat_data_msg_.reserved_3 = referee_data.power_heat_data.reserved_3;
      power_heat_data_msg_.buffer_energy = referee_data.power_heat_data.buffer_energy;
      power_heat_data_msg_.shooter_17mm_1_barrel_heat = referee_data.power_heat_data.shooter_17mm_1_barrel_heat;
      power_heat_data_msg_.shooter_42mm_barrel_heat = referee_data.power_heat_data.shooter_42mm_barrel_heat;
      power_heat_data_pub_->publish(power_heat_data_msg_);
      break;
    }
    case CmdEnum::kRobotPos: {
      robot_pos_msg_.header.stamp = get_clock()->now();
      robot_pos_msg_.x = referee_data.robot_pos.x;
      robot_pos_msg_.y = referee_data.robot_pos.y;
      robot_pos_msg_.angle = referee_data.robot_pos.angle;
      robot_pos_pub_->publish(robot_pos_msg_);
      break;
    }
    case CmdEnum::kBuff: {
      buff_msg_.header.stamp = get_clock()->now();
      buff_msg_.recovery_buff = referee_data.buff.recovery_buff;
      buff_msg_.cooling_buff = referee_data.buff.cooling_buff;
      buff_msg_.defence_buff = referee_data.buff.defence_buff;
      buff_msg_.vulnerability_buff = referee_data.buff.vulnerability_buff;
      buff_msg_.attack_buff = referee_data.buff.attack_buff;
      buff_msg_.remaining_energy = referee_data.buff.remaining_energy;
      buff_pub_->publish(buff_msg_);
      break;
    }
    case CmdEnum::kHurtData: {
      hurt_data_msg_.header.stamp = get_clock()->now();
      hurt_data_msg_.armor_id = referee_data.hurt_data.armor_id;
      hurt_data_msg_.hp_deduction_reason = referee_data.hurt_data.HP_deduction_reason;
      hurt_data_pub_->publish(hurt_data_msg_);
      break;
    }
    case CmdEnum::kShootData: {
      shoot_data_msg_.header.stamp = get_clock()->now();
      shoot_data_msg_.bullet_type = referee_data.shoot_data.bullet_type;
      shoot_data_msg_.shooter_number = referee_data.shoot_data.shooter_number;
      shoot_data_msg_.launching_frequency = referee_data.shoot_data.launching_frequency;
      shoot_data_msg_.initial_speed = referee_data.shoot_data.initial_speed;
      shoot_data_pub_->publish(shoot_data_msg_);
      break;
    }
    case CmdEnum::kProjectileAllowance: {
      projectile_allowance_msg_.header.stamp = get_clock()->now();
      projectile_allowance_msg_.projectile_allowance_17mm = referee_data.projectile_allowance.projectile_allowance_17mm;
      projectile_allowance_msg_.projectile_allowance_42mm = referee_data.projectile_allowance.projectile_allowance_42mm;
      projectile_allowance_msg_.remaining_gold_coin = referee_data.projectile_allowance.remaining_gold_coin;
      projectile_allowance_msg_.projectile_allowance_fortress =
          referee_data.projectile_allowance.projectile_allowance_fortress;
      projectile_allowance_pub_->publish(projectile_allowance_msg_);
      break;
    }
    case CmdEnum::kRfidStatus: {
      rfid_status_msg_.header.stamp = get_clock()->now();
      rfid_status_msg_.rfid_status = referee_data.rfid_status.rfid_status;
      rfid_status_msg_.rfid_status_2 = referee_data.rfid_status.rfid_status_2;
      rfid_status_pub_->publish(rfid_status_msg_);
      break;
    }
    case CmdEnum::kDartClientCmd: {
      dart_client_cmd_msg_.header.stamp = get_clock()->now();
      dart_client_cmd_msg_.dart_launch_opening_status = referee_data.dart_client_cmd.dart_launch_opening_status;
      dart_client_cmd_msg_.reserved = referee_data.dart_client_cmd.reserved;
      dart_client_cmd_msg_.target_change_time = referee_data.dart_client_cmd.target_change_time;
      dart_client_cmd_msg_.latest_launch_cmd_time = referee_data.dart_client_cmd.latest_launch_cmd_time;
      dart_client_cmd_pub_->publish(dart_client_cmd_msg_);
      break;
    }
    case CmdEnum::kGroundRobotPosition: {
      ground_robot_position_msg_.header.stamp = get_clock()->now();
      ground_robot_position_msg_.hero_x = referee_data.ground_robot_position.hero_x;
      ground_robot_position_msg_.hero_y = referee_data.ground_robot_position.hero_y;
      ground_robot_position_msg_.engineer_x = referee_data.ground_robot_position.engineer_x;
      ground_robot_position_msg_.engineer_y = referee_data.ground_robot_position.engineer_y;
      ground_robot_position_msg_.standard_3_x = referee_data.ground_robot_position.standard_3_x;
      ground_robot_position_msg_.standard_3_y = referee_data.ground_robot_position.standard_3_y;
      ground_robot_position_msg_.standard_4_x = referee_data.ground_robot_position.standard_4_x;
      ground_robot_position_msg_.standard_4_y = referee_data.ground_robot_position.standard_4_y;
      ground_robot_position_msg_.reserved = referee_data.ground_robot_position.reserved;
      ground_robot_position_msg_.reserved_2 = referee_data.ground_robot_position.reserved_2;
      ground_robot_position_pub_->publish(ground_robot_position_msg_);
      break;
    }
    case CmdEnum::kRadarMarkData: {
      radar_mark_data_msg_.header.stamp = get_clock()->now();
      radar_mark_data_msg_.mark_progress = referee_data.radar_mark_data.mark_progress;
      radar_mark_data_pub_->publish(radar_mark_data_msg_);
      break;
    }
    case CmdEnum::kSentryInfo: {
      sentry_info_msg_.header.stamp = get_clock()->now();
      sentry_info_msg_.sentry_info = referee_data.sentry_info.sentry_info;
      sentry_info_msg_.sentry_info_2 = referee_data.sentry_info.sentry_info_2;
      sentry_info_msg_.sentry_info_3 = referee_data.sentry_info.sentry_info_3;
      sentry_info_pub_->publish(sentry_info_msg_);
      break;
    }
    case CmdEnum::kRadarInfo: {
      radar_info_msg_.header.stamp = get_clock()->now();
      radar_info_msg_.radar_info = referee_data.radar_info.radar_info;
      radar_info_pub_->publish(radar_info_msg_);
      break;
    }
    case CmdEnum::kCustomRobotData: {
      custom_robot_data_msg_.header.stamp = get_clock()->now();
      memcpy(&custom_robot_data_msg_.data, referee_data.custom_robot_data.data, 30);
      custom_robot_data_pub_->publish(custom_robot_data_msg_);
      break;
    }
    case CmdEnum::kRobotCustomData: {
      robot_custom_data_msg_.header.stamp = get_clock()->now();
      memcpy(&robot_custom_data_msg_.data, referee_data.robot_custom_data.data, 30);
      robot_custom_data_pub_->publish(robot_custom_data_msg_);
      break;
    }
    case CmdEnum::kRobotCustomData2: {
      robot_custom_data_2_msg_.header.stamp = get_clock()->now();
      memcpy(&robot_custom_data_2_msg_.data, referee_data.robot_custom_data_2.data, 300);
      robot_custom_data_2_pub_->publish(robot_custom_data_2_msg_);
      break;
    }
    case CmdEnum::kCustomControl: {
      custom_control_msg_.header.stamp = get_clock()->now();
      memcpy(&custom_control_msg_.data, referee_data.custom_control.data, 30);
      custom_control_pub_->publish(custom_control_msg_);
      break;
    }
    case CmdEnum::kMapCommand: {
      map_command_msg_.header.stamp = get_clock()->now();
      map_command_msg_.target_position_x = referee_data.map_command.target_position_x;
      map_command_msg_.target_position_y = referee_data.map_command.target_position_y;
      map_command_msg_.cmd_keyboard = referee_data.map_command.cmd_keyboard;
      map_command_msg_.target_robot_id = referee_data.map_command.target_robot_id;
      map_command_msg_.cmd_source = referee_data.map_command.cmd_source;
      map_command_pub_->publish(map_command_msg_);
      break;
    }
  }
}

#include <rclcpp_components/register_node_macro.hpp>
RCLCPP_COMPONENTS_REGISTER_NODE(RefereeNode)
