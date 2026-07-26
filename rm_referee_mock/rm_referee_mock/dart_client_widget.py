#!/usr/bin/env python3

import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QSpinBox, QComboBox, QPushButton
)
from rm_referee_mock.widget_confirmed_line_edit import ConfirmedLineEdit


class DartClientWidget(QWidget):
    """Widget for dart launch system control"""

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("Dart Client")

        main_layout = QVBoxLayout()

        # Settings group
        settings_group = QGroupBox("发布设置")
        settings_layout = QFormLayout()

        self.topic_prefix_edit = ConfirmedLineEdit("/rm_referee/mock")
        self.topic_prefix_edit.setPlaceholderText("输入话题前缀")
        settings_layout.addRow("话题前缀:", self.topic_prefix_edit)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # DartInfo group (0x0105)
        dart_info_group = QGroupBox("飞镖发射相关数据 (DartInfo - 0x0105)")
        dart_info_layout = QFormLayout()

        # dart_remaining_time
        self.dart_remaining_time_spin = QSpinBox()
        self.dart_remaining_time_spin.setRange(0, 255)
        self.dart_remaining_time_spin.setValue(0)
        self.dart_remaining_time_spin.setSuffix(" 秒")
        dart_info_layout.addRow("发射剩余时间:", self.dart_remaining_time_spin)

        # dart_info bit 0-2: 最近击中目标
        self.last_hit_target_combo = QComboBox()
        self.last_hit_target_combo.addItems([
            "[0] 未击中",
            "[1] 前哨站",
            "[2] 基地固定目标",
            "[3] 基地随机固定目标",
            "[4] 基地随机移动目标",
            "[5] 基地末端移动目标"
        ])
        dart_info_layout.addRow("最近击中目标:", self.last_hit_target_combo)

        # dart_info bit 3-5: 被击中次数
        self.hit_count_spin = QSpinBox()
        self.hit_count_spin.setRange(0, 4)
        self.hit_count_spin.setValue(0)
        dart_info_layout.addRow("累计击中次数:", self.hit_count_spin)

        # dart_info bit 6-8: 选定目标
        self.selected_target_combo = QComboBox()
        self.selected_target_combo.addItems([
            "[0] 未选定/前哨站",
            "[1] 基地固定目标",
            "[2] 基地随机固定目标",
            "[3] 基地随机移动目标",
            "[4] 基地末端移动目标"
        ])
        dart_info_layout.addRow("选定击打目标:", self.selected_target_combo)

        dart_info_group.setLayout(dart_info_layout)
        main_layout.addWidget(dart_info_group)

        # DartClientCmd group (0x020A)
        dart_cmd_group = QGroupBox("飞镖选手端指令数据 (DartClientCmd - 0x020A)")
        dart_cmd_layout = QFormLayout()

        # dart_launch_opening_status
        self.launch_status_combo = QComboBox()
        self.launch_status_combo.addItems([
            "[0] 已经开启",
            "[1] 关闭",
            "[2] 正在开启或者关闭中"
        ])
        dart_cmd_layout.addRow("发射站状态:", self.launch_status_combo)

        # target_change_time
        self.target_change_time_spin = QSpinBox()
        self.target_change_time_spin.setRange(0, 65535)
        self.target_change_time_spin.setValue(0)
        self.target_change_time_spin.setSuffix(" 秒")
        dart_cmd_layout.addRow("上一次切换目标:", self.target_change_time_spin)

        # latest_launch_cmd_time
        self.latest_launch_time_spin = QSpinBox()
        self.latest_launch_time_spin.setRange(0, 65535)
        self.latest_launch_time_spin.setValue(0)
        self.latest_launch_time_spin.setSuffix(" 秒")
        dart_cmd_layout.addRow("最后发射指令时间:", self.latest_launch_time_spin)

        dart_cmd_group.setLayout(dart_cmd_layout)
        main_layout.addWidget(dart_cmd_group)

        # Quick action buttons
        action_group = QGroupBox("快捷操作")
        action_layout = QHBoxLayout()

        self.btn_reset = QPushButton("重置所有值")
        self.btn_reset.clicked.connect(self._reset_values)
        action_layout.addWidget(self.btn_reset)

        self.btn_launch_cmd = QPushButton("发射")
        self.btn_launch_cmd.clicked.connect(self._execute_launch_command)
        action_layout.addWidget(self.btn_launch_cmd)

        action_group.setLayout(action_layout)
        main_layout.addWidget(action_group)

        # Add stretch to push everything to top
        main_layout.addStretch()

        self.setLayout(main_layout)

    def _reset_values(self):
        """Reset all values to default"""
        self.dart_remaining_time_spin.setValue(0)
        self.last_hit_target_combo.setCurrentIndex(0)
        self.hit_count_spin.setValue(0)
        self.selected_target_combo.setCurrentIndex(0)
        self.launch_status_combo.setCurrentIndex(1)  # 关闭
        self.target_change_time_spin.setValue(0)
        self.latest_launch_time_spin.setValue(0)

    def _execute_launch_command(self):
        """Execute launch command - update latest launch time to current time mod 420s"""
        current_time = int(time.time())
        launch_time = 420 - (current_time % 420)
        self.latest_launch_time_spin.setValue(launch_time)

    def get_topic_prefix(self):
        """Get the topic prefix"""
        return self.topic_prefix_edit.get_confirmed_text()

    def get_dart_info_data(self):
        """Get DartInfo message data as dict"""
        # Construct dart_info uint16 according to protocol
        # bit 0-2: last hit target
        # bit 3-5: hit count
        # bit 6-8: selected target
        # bit 9-15: reserved

        dart_info_value = 0
        dart_info_value |= (
            self.last_hit_target_combo.currentIndex() & 0x07)  # bit 0-2
        dart_info_value |= (
            (self.hit_count_spin.value() & 0x07) << 3)  # bit 3-5
        dart_info_value |= (
            (self.selected_target_combo.currentIndex() & 0x07) << 6)  # bit 6-8

        return {
            'dart_remaining_time': self.dart_remaining_time_spin.value(),
            'dart_info': dart_info_value
        }

    def get_dart_client_cmd_data(self):
        """Get DartClientCmd message data as dict"""
        return {
            'dart_launch_opening_status': self.launch_status_combo.currentIndex(),
            'reserved': 0,
            'target_change_time': self.target_change_time_spin.value(),
            'latest_launch_cmd_time': self.latest_launch_time_spin.value()
        }
