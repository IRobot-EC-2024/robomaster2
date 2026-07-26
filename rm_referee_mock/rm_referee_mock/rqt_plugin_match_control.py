#!/usr/bin/env python3

import json
from os import path
from time import time

from rqt_gui_py.plugin import Plugin
# [新增] 引入 Qt 信号机制，解决多线程报错问题
from python_qt_binding.QtCore import QObject, pyqtSignal
from ament_index_python.packages import get_package_share_directory

from rm_referee_msgs.msg import (
    GameStatus, 
    GameRobotHP, 
    EventData, 
    RobotStatus, 
    ProjectileAllowance, 
    RFIDStatus,
    PowerHeatData,
    HurtData,
    RobotPos,
    SentryInfo 
)

try:
    from rclpy.time import Time
    from tf2_ros import Buffer, TransformListener
    from tf2_ros import LookupException, ConnectivityException, ExtrapolationException
except ImportError:
    Time = None
    Buffer = None
    TransformListener = None
    LookupException = ConnectivityException = ExtrapolationException = Exception

try:
    from rm_referee_msgs.srv import Tx
except ImportError:
    # 兼容性处理：如果你还没有编译好 sentry_msgs，防止插件直接崩掉
    print("Warning: Could not import SetSentryPosture service.")
    Tx = None

from rm_referee_mock.match_control_widget import MatchControlWidget
from rm_referee_mock.publisher_pool import PublisherPool
from rm_referee_mock.protocol import (
    decode_sentry_command,
    pack_sentry_info,
    truncate_sentry_command,
)


# [新增] 创建一个用于跨线程通信的桥接类
class WorkerSignals(QObject):
    # 定义信号：完整的 0x0120 sentry_cmd 解包结果
    update_sentry_signal = pyqtSignal(object)


class MatchControlPlugin(Plugin):
    """RQt Plugin wrapper for MatchControlWidget"""

    def __init__(self, context):
        super(MatchControlPlugin, self).__init__(context)
        self.setObjectName("MatchControlPlugin")

        self._widget = MatchControlWidget()

        if context.serial_number() > 1:
            self._widget.setWindowTitle(
                self._widget.windowTitle() + (" (%d)" % context.serial_number()))

        context.add_widget(self._widget)
        self._node = context.node
        self._publisher_pool = PublisherPool(self._node)
        self._load_supply_points()

        # [关键] 初始化信号桥接，绑定 UI 更新函数
        # 这样可以将 ROS 线程收到的数据安全地传给主线程进行 UI 更新
        self.signals = WorkerSignals()
        self.signals.update_sentry_signal.connect(self._ui_update_callback)

        # === Service Server 初始化 ===
        if Tx:
            self._srv = self._node.create_service(
                Tx, 
                '/rm_referee/tx', 
                self._handle_sentry_cmd
            )
            
        self._robot_pos_subscriptions = [
            self._node.create_subscription(
                RobotPos,
                '/rm_referee/robot_pos',
                self._handle_robot_pos,
                10,
            ),
            self._node.create_subscription(
                RobotPos,
                '/rm_referee/mock/robot_pos',
                self._handle_robot_pos,
                10,
            ),
        ]
        self._tf_buffer = None
        self._tf_listener = None
        self._init_tf_listener()

        self._timer = self._node.create_timer(0.1, self._timer_callback)

    def _load_supply_points(self):
        try:
            waypoint_path = path.join(
                get_package_share_directory("sentry_nav_bt_test"),
                "config",
                "waypoints.json",
            )
            with open(waypoint_path, "r", encoding="utf-8") as waypoint_file:
                waypoint_data = json.load(waypoint_file)

            wanted_names = {"supply_point", "supply_point_2"}
            points = []
            for waypoint in waypoint_data.get("waypoints", []):
                name = waypoint.get("name")
                if name in wanted_names:
                    points.append((name, waypoint["x"], waypoint["y"]))

            if points:
                self._widget.set_auto_supply_points(points)
                self._node.get_logger().info(
                    f"[Supply] 已加载补给点: {', '.join(point[0] for point in points)}"
                )
        except Exception as exc:
            self._node.get_logger().warn(
                f"[Supply] 未能从 sentry_nav_bt_test 加载补给点，使用 mock 默认值: {exc}"
            )

    def _init_tf_listener(self):
        if Buffer is None or TransformListener is None:
            self._node.get_logger().warn("[Supply] tf2_ros 不可用，补给区自动检测仅使用 RobotPos")
            return

        try:
            self._tf_buffer = Buffer()
            self._tf_listener = TransformListener(self._tf_buffer, self._node)
        except Exception as exc:
            self._tf_buffer = None
            self._tf_listener = None
            self._node.get_logger().warn(f"[Supply] TF 监听初始化失败: {exc}")

    def _handle_robot_pos(self, msg):
        self._widget.update_auto_supply_pose(msg.x, msg.y, "robot_pos")

    def _update_auto_supply_pose_from_tf(self):
        if self._tf_buffer is None or Time is None:
            return

        try:
            transform = self._tf_buffer.lookup_transform("map", "base_link", Time())
        except (LookupException, ConnectivityException, ExtrapolationException):
            return
        except Exception:
            return

        translation = transform.transform.translation
        self._widget.update_auto_supply_pose(translation.x, translation.y, "tf")

    def _truncate_sentry_cmd_for_protocol(self, parsed_cmd):
        current = {
            "exchange_projectile": self._widget.spinBox_sentry_exchange_projectile.value(),
            "remote_projectile_exchange_count":
                self._widget.spinBox_sentry_remote_projectile_exchange.value(),
            "remote_hp_exchange_count":
                self._widget.spinBox_sentry_remote_hp_exchange.value(),
        }
        return truncate_sentry_command(parsed_cmd, current)

    def _handle_sentry_cmd(self, request, response):
        """
        处理收到的 Service 请求 (解析 C++ 发来的原始协议包)
        协议包结构: Header(5) + CmdID(2) + [SubHeader(6) + Content(4)] + CRC16(2) = 19 bytes
        关键数据在 Content (4 bytes)，位于 offset 13 (5+2+6)
        """
        raw_data = request.data
        data_len = len(raw_data)

        # [调试] 收到原始数据，证明 Service 链路是通的
        self._node.get_logger().info(f"[Service-Rx] 收到请求, 长度: {data_len} 字节")
        
        # 简单校验长度 (至少要有19字节)
        if data_len < 19:
            self._node.get_logger().warn(f"[Service-Error] 数据包长度不足! 收到: {data_len}, 期望: >=19")
            response.ok = False
            return response

        try:
            cmd_id = int.from_bytes(bytes(raw_data[5:7]), byteorder="little", signed=False)
            data_cmd_id = int.from_bytes(bytes(raw_data[7:9]), byteorder="little", signed=False)
            if cmd_id != 0x0301 or data_cmd_id != 0x0120:
                self._node.get_logger().warn(
                    f"[Service-Ignore] 非哨兵 0x0120 指令, cmd_id=0x{cmd_id:04X}, data_cmd_id=0x{data_cmd_id:04X}"
                )
                response.header.stamp = self._node.get_clock().now().to_msg()
                response.header.frame_id = "referee_mock"
                response.ok = False
                return response

            sentry_cmd = int.from_bytes(bytes(raw_data[13:17]), byteorder="little", signed=False)
            parsed_cmd = decode_sentry_command(sentry_cmd)

            self._node.get_logger().info(
                "[Service-Parse] 解析成功 -> "
                f"free_revive={parsed_cmd['confirm_free_revive']}, "
                f"buy_revive={parsed_cmd['confirm_buy_revive']}, "
                f"ammo_target={parsed_cmd['exchange_projectile']}, "
                f"remote_ammo_req={parsed_cmd['remote_projectile_exchange_count']}, "
                f"remote_hp_req={parsed_cmd['remote_hp_exchange_count']}, "
                f"posture={parsed_cmd['posture']}, "
                f"activate={parsed_cmd['activate_rune']}"
            )

            processed_cmd, truncate_reason = self._truncate_sentry_cmd_for_protocol(parsed_cmd)
            if truncate_reason:
                self._node.get_logger().warn(
                    f"[Protocol-Truncate] {truncate_reason}；仅处理该字段前面的低位指令"
                )

            self.signals.update_sentry_signal.emit(processed_cmd)
            
            response.header.stamp = self._node.get_clock().now().to_msg()
            response.header.frame_id = "referee_mock"

            response.ok = True 

        except Exception as e:
            self._node.get_logger().error(f"[Service-Exception] 解析或处理错误: {str(e)}")
            response.ok = False

        return response

    def _ui_update_callback(self, sentry_cmd):
        """
        [主线程] 这个函数由 Qt 信号触发，专门负责更新 UI
        """
        try:
            can_continue = True

            if sentry_cmd["confirm_free_revive"] == 1:
                success, message = self._widget.confirm_free_revive()
                if success:
                    self._node.get_logger().info(f">>> [UI-Success] {message}")
                else:
                    self._node.get_logger().warn(f">>> [UI-Fail] {message}")
                    can_continue = False

            if can_continue and sentry_cmd["confirm_buy_revive"] == 1:
                success, message = self._widget.confirm_buy_revive()
                if success:
                    self._node.get_logger().info(f">>> [UI-Success] {message}")
                else:
                    self._node.get_logger().warn(f">>> [UI-Fail] {message}")
                    can_continue = False

            if not can_continue:
                return

            exchange_projectile_target = int(sentry_cmd.get("exchange_projectile", 0))
            if exchange_projectile_target > 0:
                success, message = self._widget.confirm_projectile_exchange(exchange_projectile_target)
                if success:
                    self._node.get_logger().info(f">>> [UI-Success] {message}")
                else:
                    self._node.get_logger().warn(f">>> [UI-Fail] {message}")
                    return

            remote_projectile_target = int(sentry_cmd.get("remote_projectile_exchange_count", 0))
            if remote_projectile_target > self._widget.spinBox_sentry_remote_projectile_exchange.value():
                self._widget.spinBox_sentry_remote_projectile_exchange.setValue(remote_projectile_target)
                self._node.get_logger().info(
                    f">>> [UI-Success] 远程补弹请求次数回显为 {remote_projectile_target}"
                )

            remote_hp_target = int(sentry_cmd.get("remote_hp_exchange_count", 0))
            if remote_hp_target > self._widget.spinBox_sentry_remote_hp_exchange.value():
                self._widget.spinBox_sentry_remote_hp_exchange.setValue(remote_hp_target)
                self._node.get_logger().info(
                    f">>> [UI-Success] 远程回血请求次数回显为 {remote_hp_target}"
                )

            posture_val = int(sentry_cmd.get("posture", 0))
            if posture_val in (1, 2, 3, 4, 5, 6):
                accepted, message = self._widget.request_sentry_posture(posture_val)
                if accepted:
                    self._node.get_logger().info(f">>> [UI-Success] 姿态请求: {message}")
                else:
                    # Tx.response.ok 只表示链路成功；语义拒绝通过不改变 0x020D 回显体现。
                    self._node.get_logger().warn(f">>> [UI-Semantic-Reject] {message}")
                    return

            if sentry_cmd["activate_rune"] == 1:
                self._node.get_logger().info("[UI-Logic] 收到激活请求，调用 Widget 逻辑...")
                success = self._widget.confirm_activation()
                if success:
                    self._node.get_logger().info(">>> [UI-Success] 激活成功！倒计时开始")
                else:
                    self._node.get_logger().warn(">>> [UI-Fail] 激活被拒绝！(无权限/冷却中)")
            
        except Exception as e:
            self._node.get_logger().error(f"[UI-Exception] UI 更新出错: {str(e)}")

    def _timer_callback(self):
        """Timer callback to publish match status periodically"""
        self._update_auto_supply_pose_from_tf()

        # Get current status from widget
        status = self._widget.get_game_status()
        topic_prefix = self._widget.get_topic_prefix()

        current_time_msg = self._node.get_clock().now().to_msg()

        # Publish GameStatus message
        game_status_msg = GameStatus()
        game_status_msg.header.stamp = current_time_msg
        game_status_msg.header.frame_id = "referee_system"
        game_status_msg.game_type = int(status["game_type"])
        game_status_msg.game_progress = int(status["game_progress"])
        game_status_msg.stage_remain_time = int(status["stage_remain_time"])
        game_status_msg.sync_timestamp = int(time() * 1000)

        self._publisher_pool.publish(
            f"{topic_prefix}/game_status", GameStatus, game_status_msg)

        # Publish GameRobotHP message
        robot_hp_msg = GameRobotHP()
        robot_hp_msg.header.stamp = current_time_msg
        robot_hp_msg.header.frame_id = "referee_system"
        robot_hp_msg.ally_1_robot_hp = int(status["robot_hp"]["hero"])
        robot_hp_msg.ally_2_robot_hp = int(status["robot_hp"]["engineer"])
        robot_hp_msg.ally_3_robot_hp = int(status["robot_hp"]["infantry_3"])
        robot_hp_msg.ally_4_robot_hp = int(status["robot_hp"]["infantry_4"])
        robot_hp_msg.damage_difference = int(status["robot_hp"]["damage_difference"])
        robot_hp_msg.ally_7_robot_hp = int(status["robot_hp"]["sentry"])
        robot_hp_msg.ally_outpost_hp = int(status["robot_hp"]["ally_outpost"])
        robot_hp_msg.ally_base_hp = int(status["robot_hp"]["ally_base"])
        robot_hp_msg.enemy_outpost_hp = int(status["robot_hp"]["enemy_outpost"])
        robot_hp_msg.enemy_base_hp = int(status["robot_hp"]["enemy_base"])

        self._publisher_pool.publish(
            f"{topic_prefix}/game_robot_hp", GameRobotHP, robot_hp_msg)
        
        # [新增] Publish EventData 
        event_msg = EventData()
        event_msg.header.stamp = current_time_msg
        event_msg.header.frame_id = "referee_system"
        event_msg.event_data = int(status["event_data"]) 
        self._publisher_pool.publish(
            f"{topic_prefix}/event_data", EventData, event_msg)

        # Publish RFIDStatus
        rfid_status = status.get("rfid_status", {})
        rfid_msg = RFIDStatus()
        rfid_msg.header.stamp = current_time_msg
        rfid_msg.header.frame_id = "referee_system"
        rfid_msg.rfid_status = int(rfid_status.get("rfid_status", 0))
        rfid_msg.rfid_status_2 = int(rfid_status.get("rfid_status_2", 0))
        self._publisher_pool.publish(
            f"{topic_prefix}/rfid_status", RFIDStatus, rfid_msg)
            
        # [新增] Publish RobotStatus 
        robot_status_msg = RobotStatus()
        robot_status_msg.header.stamp = current_time_msg
        robot_status_msg.header.frame_id = "referee_system"
        robot_status_msg.robot_id = int(status["robot_status"]["id"])
        robot_status_msg.robot_level = 1
        robot_status_msg.current_hp = int(status["robot_status"]["current_hp"])
        robot_status_msg.maximum_hp = int(status["robot_status"]["max_hp"])
        robot_status_msg.shooter_barrel_cooling_value = 0
        robot_status_msg.shooter_barrel_heat_limit = 100
        robot_status_msg.chassis_power_limit = int(status["robot_status"].get("chassis_power_limit", 120))
        # 假定功率管理都开启
        robot_status_msg.power_management_gimbal_output = True
        robot_status_msg.power_management_chassis_output = True
        robot_status_msg.power_management_shooter_output = bool(
            status["robot_status"].get("shooter_output", True))
        self._publisher_pool.publish(
            f"{topic_prefix}/robot_status", RobotStatus, robot_status_msg)

        # Publish PowerHeatData
        power_heat_status = status.get("power_heat_data", {})
        power_heat_msg = PowerHeatData()
        power_heat_msg.header.stamp = current_time_msg
        power_heat_msg.header.frame_id = "referee_system"
        power_heat_msg.reserved = 0
        power_heat_msg.reserved_2 = 0
        power_heat_msg.reserved_3 = 0.0
        power_heat_msg.buffer_energy = int(power_heat_status.get("buffer_energy", 0))
        power_heat_msg.shooter_17mm_1_barrel_heat = int(
            power_heat_status.get("shooter_17mm_1_barrel_heat", 0))
        power_heat_msg.shooter_42mm_barrel_heat = int(
            power_heat_status.get("shooter_42mm_barrel_heat", 0))
        self._publisher_pool.publish(
            f"{topic_prefix}/power_heat_data", PowerHeatData, power_heat_msg)

        # [新增] Publish ProjectileAllowance 
        ammo_msg = ProjectileAllowance()
        ammo_msg.header.stamp = current_time_msg
        ammo_msg.header.frame_id = "referee_system"
        projectile_allowance = status.get("projectile_allowance", {})
        ammo_msg.projectile_allowance_17mm = int(
            projectile_allowance.get("projectile_allowance_17mm", status["robot_status"]["ammo"]))
        ammo_msg.projectile_allowance_42mm = int(projectile_allowance.get("projectile_allowance_42mm", 0))
        ammo_msg.remaining_gold_coin = int(projectile_allowance.get("remaining_gold_coin", 0))
        ammo_msg.projectile_allowance_fortress = int(
            projectile_allowance.get("projectile_allowance_fortress", 0))
        self._publisher_pool.publish(
            f"{topic_prefix}/projectile_allowance", ProjectileAllowance, ammo_msg)
            
        # [新增] Publish HurtData (Triggered)
        if status["hurt_data"]["trigger"]:
            hurt_msg = HurtData()
            hurt_msg.header.stamp = current_time_msg
            hurt_msg.header.frame_id = "referee_system"
            hurt_msg.armor_id = int(status["hurt_data"]["armor_id"])
            hurt_msg.hp_deduction_reason = 0 # 默认为0，装甲板受击
            self._publisher_pool.publish(
                f"{topic_prefix}/hurt_data", HurtData, hurt_msg)

        # [新增] Publish SentryInfo (Echo Service Result)
        sentry_info_msg = SentryInfo()
        sentry_info_msg.header.stamp = current_time_msg
        sentry_info_msg.header.frame_id = "referee_system"

        sentry_status = status.get("sentry_info", {})
        packed_info, packed_info_2, packed_info_3 = pack_sentry_info(sentry_status)
        sentry_info_msg.sentry_info = packed_info
        sentry_info_msg.sentry_info_2 = packed_info_2
        sentry_info_msg.sentry_info_3 = packed_info_3
        
        self._publisher_pool.publish(
            f"{topic_prefix}/sentry_info", SentryInfo, sentry_info_msg)

    def shutdown_plugin(self):
        """Clean up when plugin is closed"""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def save_settings(self, plugin_settings, instance_settings):
        """Save the plugin settings"""
        for widget in self._widget.findChildren(QObject):
            object_name = widget.objectName()
            if not object_name:
                continue

            if hasattr(widget, "currentIndex") and callable(widget.currentIndex):
                instance_settings.set_value(object_name, widget.currentIndex())
            elif hasattr(widget, "value") and callable(widget.value):
                instance_settings.set_value(object_name, widget.value())
            elif hasattr(widget, "isChecked") and callable(widget.isChecked):
                instance_settings.set_value(object_name, widget.isChecked())
            elif object_name.startswith("lineEdit_"):
                value = (
                    widget.get_confirmed_text()
                    if hasattr(widget, "get_confirmed_text")
                    else widget.text()
                )
                instance_settings.set_value(object_name, value)

    def restore_settings(self, plugin_settings, instance_settings):
        """Restore the plugin settings"""
        # TODO: Restore widget state, if needed
        pass
