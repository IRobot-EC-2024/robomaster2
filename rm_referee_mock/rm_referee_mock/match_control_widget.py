#!/usr/bin/env python3

import sys
from os import path

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QTimer
from rm_referee_mock.match_control_posture import MatchControlPosture
from rm_referee_mock.match_control_resurrection import MatchControlResurrection
from rm_referee_mock.match_control_rune import MatchControlRune
from rm_referee_mock.match_control_status import MatchControlStatus
from rm_referee_mock.match_control_supply import MatchControlSupply
from rm_referee_mock.match_control_timing import MatchControlTiming
from rm_referee_mock.match_control_ui import MatchControlUi
from rm_referee_mock.sentry_posture import SentryPostureState

from ament_index_python.packages import get_package_share_directory

PACKAGE_SHARE = get_package_share_directory("rm_referee_mock")


class MatchControlWidget(
    MatchControlTiming,
    MatchControlRune,
    MatchControlResurrection,
    MatchControlSupply,
    MatchControlUi,
    MatchControlPosture,
    MatchControlStatus,
    QtWidgets.QWidget,
):
    DEFAULT_MATCH_REMAIN_SECONDS = 420
    DEFAULT_CHASSIS_POWER_LIMIT = 120
    DEFAULT_BUFFER_ENERGY_LIMIT = 60
    DEFAULT_SUPPLY_POINTS = (
        ("supply_point", -0.87, -5.04),
        ("supply_point_2", -1.35, -6.63),
    )
    SUPPLY_DETECT_RADIUS_M = 0.35
    SUPPLY_HEAL_HP_PER_SECOND = 100
    SUPPLY_PROJECTILE_PER_MINUTE = 100
    SUPPLY_PROJECTILE_MAX_MINUTES = 6
    GOLD_INITIAL_FLOOR = 400
    GOLD_TIMED_INCOME = (
        ("05:59", 359, 50),
        ("04:59", 299, 50),
        ("03:59", 239, 50),
        ("02:59", 179, 50),
        ("01:59", 119, 50),
        ("00:59", 59, 150),
    )
    RUNE_ACTIVATING_WINDOW_SECONDS = 20
    PRE_MATCH_STAGE_DURATIONS = {2: 15, 3: 5}
    MATCH_STAGE_INDEX = 4
    FINISHED_STAGE_INDEX = 5
    RMUL_GAME_TYPES = {4, 5}

    def __init__(self):
        super().__init__()

        ui_file = path.join(PACKAGE_SHARE, "assets", "match_control.ui")
        uic.loadUi(ui_file, self)
        self.setWindowTitle("Match Control")

        self.stage_countdown_remaining = 0
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_time)
        self.hurt_burst_timer = QTimer(self)
        self.hurt_burst_timer.setInterval(500)
        self.hurt_burst_timer.timeout.connect(self._emit_hurt_burst)
        self.hurt_burst_remaining = 0
        self.sentry_posture = SentryPostureState(cooldown_seconds=5.0)
        self._suppress_posture_ui_change = False

        self.current_hurt_armor_id = 0
        self.trigger_hurt = False
        self.sentry_can_activate_flag = False
        self.small_rune_chances = 0
        self.big_rune_chances = 0
        self.last_remain_seconds = -1
        self.rune_window_timers = {"small": 0, "big": 0}
        self._suppress_rune_status_change = False
        self._last_sentry_hp = None
        self.resurrection_active = False
        self.resurrection_required_seconds = 0
        self.resurrection_progress = 0
        self.buy_revive_count = 0
        self.sentry_weak_active = False
        self.sentry_invincible_remaining_seconds = 0
        self.chassis_power_boost_remaining_seconds = 0
        self.shooter_17mm_heat = 0
        self.shooter_42mm_heat = 0
        self.buffer_energy = self.DEFAULT_BUFFER_ENERGY_LIMIT
        self.auto_supply_points = list(self.DEFAULT_SUPPLY_POINTS)
        self.auto_supply_pose = None
        self.auto_supply_zone_detected = False
        self.auto_supply_zone_name = ""
        self.supply_projectile_claimed = 0
        self.gold_income_claimed = set()

        self.init_ui()

    def init_ui(self):
        """初始化 UI 控件的默认值和选项"""
        self.resize(1310, 720)
        self.setMinimumSize(1310, 720)

        # 设置比赛类型选项 (索引0不使用，从1开始)
        self.comboBox_game_type.addItems([
            "[0] 未定义",
            "[1] RoboMaster 机甲大师超级对抗赛",
            "[2] RoboMaster 机甲大师高校单项赛",
            "[3] ICRA RoboMaster高校人工智能挑战赛",
            "[4] RoboMaster机甲大师高校联盟赛3V3对抗",
            "[5] RoboMaster 机甲大师高校联盟赛步兵对抗"
        ])
        self.comboBox_game_type.setCurrentIndex(1)  # 默认选择RMUC

        # 设置比赛阶段选项
        self.comboBox_game_stage.addItems([
            "[0] 未开始比赛",
            "[1] 准备阶段",
            "[2] 十五秒裁判系统自检阶段",
            "[3] 五秒倒计时",
            "[4] 比赛中",
            "[5] 比赛结算中"
        ])

        # 设置能量机关状态选项
        # 0:未激活, 1:激活中, 2:已激活
        energy_status = ["未激活", "激活中", "已激活"]
        self.comboBox_small_rune.addItems(energy_status)  # 小能量机关
        self.comboBox_big_rune.addItems(energy_status)  # 大能量机关
        self.comboBox_small_rune.currentIndexChanged.connect(
            lambda index, rune_name="small": self._on_rune_status_changed(rune_name, index)
        )
        self.comboBox_big_rune.currentIndexChanged.connect(
            lambda index, rune_name="big": self._on_rune_status_changed(rune_name, index)
        )

        # 设置高地占领状态
        occupy_status = ["无占领", "己方占领", "敌方占领"]
        self.comboBox_central_highland.addItems(occupy_status)  # 己方中央高地

        # 设置增益点状态
        shared_buff_status = ["未被占领", "己方占领", "对方占领", "双方占领"]
        outpost_buff_status = ["未被占领", "己方占领", "对方占领"]
        self.comboBox_central_buff.addItems(shared_buff_status)  # 中心增益点
        self.comboBox_fortress_buff.addItems(shared_buff_status)  # 己方堡垒增益点
        self.comboBox_outpost_buff.addItems(outpost_buff_status)  # 己方前哨站增益点

        # 设置飞镖击中目标
        dart_targets = [
            "未击中",
            "前哨站",
            "基地固定目标",
            "基地随机固定目标",
            "基地随机移动目标",
            "基地末端移动目标",
        ]
        self.comboBox_dart_target.addItems(dart_targets)

        # 设置HP默认值
        self.spinBox_hp_1.setMaximum(200)    # 英雄   近战优先1级上限血量200 ，远程优先1级上限血量150
        self.spinBox_hp_2.setMaximum(250)  # 工程
        self.spinBox_hp_3.setMaximum(250)  # 步兵
        self.spinBox_hp_4.setMaximum(250)  # 步兵
        self.spinBox_hp_7.setMaximum(400)  # 哨兵
        self.spinBox_hp_outpost.setMaximum(1500)  # 前哨站
        self.spinBox_hp_base.setMaximum(5000)  # 基地

        # 设置初始HP值
        self.spinBox_hp_1.setValue(200)
        self.spinBox_hp_2.setValue(250)
        self.spinBox_hp_3.setValue(250)
        self.spinBox_hp_4.setValue(250)
        self.spinBox_hp_7.setValue(400)
        self.spinBox_hp_outpost.setValue(1500)
        self.spinBox_hp_base.setValue(5000)

        self.pushButton_playpause.clicked.connect(self.on_play_pause_clicked)
        self.comboBox_game_stage.currentIndexChanged.connect(self._on_game_stage_changed)

        if hasattr(self, 'btn_send_hurt'):
            self.btn_send_hurt.clicked.connect(self.on_hurt_button_clicked)

        self._replace_lineedit_with_confirmed("lineEdit_time", "7:00")
        self._replace_lineedit_with_confirmed("lineEdit_topic_prefix", "/rm_referee")
        self._replace_lineedit_with_confirmed("lineEdit_dart_time", "0:00")

        if not hasattr(self, 'spinBox_ammo'):
            self.spinBox_ammo = QtWidgets.QSpinBox()
        if not hasattr(self, 'spinBox_ammo_42mm'):
            self.spinBox_ammo_42mm = None
        if not hasattr(self, 'spinBox_gold_coin'):
            self.spinBox_gold_coin = None
        if not hasattr(self, 'spinBox_ammo_fortress'):
            self.spinBox_ammo_fortress = None
        if not hasattr(self, 'comboBox_robot_id'):
            self.comboBox_robot_id = QtWidgets.QComboBox()
        if self.comboBox_robot_id.count() == 0:
            self.comboBox_robot_id.addItem("7 - 红方哨兵", 7)
            self.comboBox_robot_id.addItem("107 - 蓝方哨兵", 107)
        self._setup_projectile_allowance_inputs()
        self._setup_sentry_info_inputs()
        self._setup_v2_game_hp_inputs()

        if hasattr(self, "checkBox"):
            self.checkBox.setChecked(False)
            self.checkBox.setEnabled(False)
            self.checkBox.setText("资源区(协议废弃)")
            self.checkBox.setToolTip("V1.3.0 中 event_data bit1 已保留，该控件不再参与编码")

        self.label_stage_countdown = QtWidgets.QLabel(self)
        self.label_stage_countdown.setObjectName("label_stage_countdown")
        self.label_stage_countdown.setGeometry(430, 515, 210, 20)
        self.label_stage_countdown.setStyleSheet("color: #666666;")
        self._on_game_stage_changed(self.comboBox_game_stage.currentIndex())

    def _reset_enemy_hp(self):
        self.spinBox_enemy_outpost_hp.setValue(1500)
        self.spinBox_enemy_base_hp.setValue(5000)

    def _simulate_heat_shot(self):
        self.spinBox_test_shooter_heat.setValue(
            min(self.spinBox_test_shooter_heat.maximum(), self.shooter_17mm_heat + 10))

    def _start_hurt_burst(self):
        self.hurt_burst_remaining = 3
        self._emit_hurt_burst()
        self.hurt_burst_timer.start()

    def _emit_hurt_burst(self):
        if self.hurt_burst_remaining <= 0:
            self.hurt_burst_timer.stop()
            return
        self.current_hurt_armor_id = self.spinBox_hurt_armor_id.value()
        self.trigger_hurt = True
        self.hurt_burst_remaining -= 1

    def on_hurt_button_clicked(self):
        """点击发送伤害"""
        self.trigger_hurt = True
        self.current_hurt_armor_id = self.spinBox_hurt_armor_id.value()
        
        
    def _reset_hurt_trigger(self):
        self.trigger_hurt = False

def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MatchControlWidget()
    window.setWindowTitle("RM Match Server Sim")
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
