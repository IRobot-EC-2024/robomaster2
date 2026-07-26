from PyQt5 import QtWidgets

from rm_referee_mock.sentry_posture import POSTURE_NAMES
from rm_referee_mock.widget_confirmed_line_edit import ConfirmedLineEdit


class MatchControlUi:
    def _replace_lineedit_with_confirmed(self, object_name, default_text):
        old_widget = getattr(self, object_name, None)
        if old_widget is None:
            print(f"Warning: {object_name} not found")
            return

        parent = old_widget.parent()
        if parent is None:
            print(f"Warning: {object_name} has no parent")
            return

        new_widget = ConfirmedLineEdit(parent)
        new_widget.setObjectName(object_name)
        new_widget.setText(default_text)
        new_widget.set_confirmed_text(default_text)
        new_widget.setEnabled(old_widget.isEnabled())
        new_widget.setReadOnly(old_widget.isReadOnly())
        new_widget.setPlaceholderText(old_widget.placeholderText())
        new_widget.setSizePolicy(old_widget.sizePolicy())
        new_widget.setMinimumSize(old_widget.minimumSize())
        new_widget.setMaximumSize(old_widget.maximumSize())

        layout = parent.layout()
        if layout:
            for i in range(layout.count()):
                if layout.itemAt(i).widget() == old_widget:
                    layout.removeWidget(old_widget)
                    layout.insertWidget(i, new_widget)
                    break
        else:
            new_widget.setGeometry(old_widget.geometry())

        old_widget.hide()
        old_widget.deleteLater()
        setattr(self, object_name, new_widget)
        new_widget.show()

    def _ensure_labeled_spinbox(self, parent_widget, layout, insert_index, label_name, label_text, spinbox_name,
                                maximum=65535, default_value=0):
        spinbox = getattr(self, spinbox_name, None)
        if spinbox is None:
            label = QtWidgets.QLabel(parent_widget)
            label.setObjectName(label_name)
            label.setText(label_text)
            spinbox = QtWidgets.QSpinBox(parent_widget)
            spinbox.setObjectName(spinbox_name)
            spinbox.setValue(default_value)
            layout.insertWidget(insert_index, label)
            layout.insertWidget(insert_index + 1, spinbox)
            setattr(self, label_name, label)
            setattr(self, spinbox_name, spinbox)

        spinbox.setMaximum(maximum)
        return spinbox

    def _move_widget_to_layout(self, widget, target_layout):
        if widget is None:
            return

        current_parent = widget.parent()
        current_layout = current_parent.layout() if current_parent else None
        if current_layout is not None:
            current_layout.removeWidget(widget)

        target_parent = target_layout.parentWidget()
        if widget.parent() is not target_parent:
            widget.setParent(target_parent)

        if target_layout.indexOf(widget) == -1:
            target_layout.addWidget(widget)
        widget.show()

    def _ensure_projectile_allowance_group(self):
        group = getattr(self, "groupBox_projectile_allowance", None)
        layout = getattr(self, "verticalLayout_projectile_allowance", None)
        if group is None:
            group = QtWidgets.QGroupBox(self)
            group.setObjectName("groupBox_projectile_allowance")
            group.setTitle("ProjectileAllowance")
            setattr(self, "groupBox_projectile_allowance", group)

        if layout is None:
            layout = group.layout()
            if layout is None:
                layout = QtWidgets.QVBoxLayout(group)
            layout.setObjectName("verticalLayout_projectile_allowance")
            setattr(self, "verticalLayout_projectile_allowance", layout)

        return group, layout

    def _setup_projectile_allowance_inputs(self):
        self.spinBox_ammo.setMaximum(65535)

        if not hasattr(self, "verticalLayout_rs") or not hasattr(self, "groupBox_robot_status"):
            return

        projectile_group, projectile_layout = self._ensure_projectile_allowance_group()

        if not hasattr(self, "label_ammo"):
            self.label_ammo = QtWidgets.QLabel(projectile_group)
            self.label_ammo.setObjectName("label_ammo")
            self.label_ammo.setText("17mm弹丸")
        self._move_widget_to_layout(self.label_ammo, projectile_layout)
        self._move_widget_to_layout(self.spinBox_ammo, projectile_layout)

        self.spinBox_ammo_42mm = self._ensure_labeled_spinbox(
            projectile_group, projectile_layout, 2, "label_ammo_42mm", "42mm弹丸", "spinBox_ammo_42mm")
        self.spinBox_gold_coin = self._ensure_labeled_spinbox(
            projectile_group, projectile_layout, 4, "label_gold_coin", "剩余金币", "spinBox_gold_coin")
        self.spinBox_ammo_fortress = self._ensure_labeled_spinbox(
            projectile_group, projectile_layout, 6, "label_ammo_fortress", "堡垒17mm", "spinBox_ammo_fortress")

        self.groupBox_robot_status.setTitle("RobotStatus")
        if not hasattr(self, "checkBox_shooter_output"):
            self.checkBox_shooter_output = QtWidgets.QCheckBox(self.groupBox_robot_status)
            self.checkBox_shooter_output.setObjectName("checkBox_shooter_output")
        self.checkBox_shooter_output.setText("发射输出")
        self.checkBox_shooter_output.setToolTip(
            "发布 RobotStatus.power_management_shooter_output；取消勾选发布 0")
        self.checkBox_shooter_output.setChecked(True)
        self._move_widget_to_layout(self.checkBox_shooter_output, self.verticalLayout_rs)

        self.groupBox_robot_status.setGeometry(650, 20, 120, 120)
        projectile_group.setGeometry(650, 150, 120, 180)
        if hasattr(self, "groupBox_hurt"):
            self.groupBox_hurt.setGeometry(650, 340, 120, 120)
        if hasattr(self, "groupBox_service_echo"):
            self.groupBox_service_echo.setGeometry(650, 460, 120, 160)

    def _create_sentry_spinbox(self, maximum):
        spinbox = QtWidgets.QSpinBox(self.groupBox_sentry_detail)
        spinbox.setMaximum(maximum)
        spinbox.setValue(0)
        return spinbox

    def _setup_sentry_info_inputs(self):
        if not hasattr(self, "groupBox_service_echo") or not hasattr(self, "verticalLayout_echo"):
            return

        self.groupBox_service_echo.setTitle("Sentry Echo")
        self.label_echo_title.setText("当前姿态:")
        self.label_sentry_mode.setText("姿态: -")
        self.checkBox_can_activate_rune.setText("手动强制可打符")
        self.checkBox_can_activate_rune.setChecked(False)
        self.checkBox_can_activate_rune.setToolTip("用于调试时手动将 sentry_info_2 bit14 置 1")

        self.label_sentry_auto_activate = QtWidgets.QLabel(self.groupBox_service_echo)
        self.label_sentry_auto_activate.setObjectName("label_sentry_auto_activate")
        self.verticalLayout_echo.insertWidget(2, self.label_sentry_auto_activate)

        self.label_rune_window_status = QtWidgets.QLabel(self.groupBox_service_echo)
        self.label_rune_window_status.setObjectName("label_rune_window_status")
        self.verticalLayout_echo.insertWidget(3, self.label_rune_window_status)

        self.groupBox_sentry_detail = QtWidgets.QGroupBox(self)
        self.groupBox_sentry_detail.setObjectName("groupBox_sentry_detail")
        self.groupBox_sentry_detail.setTitle("SentryInfo 0x020D")
        self.groupBox_sentry_detail.setGeometry(780, 20, 230, 330)

        form_layout = QtWidgets.QFormLayout(self.groupBox_sentry_detail)
        form_layout.setObjectName("formLayout_sentry_detail")

        self.spinBox_sentry_exchange_projectile = self._create_sentry_spinbox(2047)
        self.spinBox_sentry_remote_projectile_exchange = self._create_sentry_spinbox(15)
        self.spinBox_sentry_remote_hp_exchange = self._create_sentry_spinbox(15)
        self.checkBox_sentry_can_free_revive = QtWidgets.QCheckBox(self.groupBox_sentry_detail)
        self.checkBox_sentry_can_buy_revive = QtWidgets.QCheckBox(self.groupBox_sentry_detail)
        self.spinBox_sentry_buy_revive_cost = self._create_sentry_spinbox(1023)
        self.checkBox_sentry_is_disengaged = QtWidgets.QCheckBox(self.groupBox_sentry_detail)
        self.spinBox_sentry_team_projectile_exchange = self._create_sentry_spinbox(2047)

        form_layout.addRow("成功补弹", self.spinBox_sentry_exchange_projectile)
        form_layout.addRow("远程补弹次数", self.spinBox_sentry_remote_projectile_exchange)
        form_layout.addRow("远程回血次数", self.spinBox_sentry_remote_hp_exchange)
        form_layout.addRow("可免费复活", self.checkBox_sentry_can_free_revive)
        form_layout.addRow("可金币复活", self.checkBox_sentry_can_buy_revive)
        form_layout.addRow("金币复活花费", self.spinBox_sentry_buy_revive_cost)
        form_layout.addRow("当前脱战", self.checkBox_sentry_is_disengaged)
        form_layout.addRow("队伍剩余可兑17mm", self.spinBox_sentry_team_projectile_exchange)

        self.label_resurrection_status = QtWidgets.QLabel(self.groupBox_sentry_detail)
        self.label_resurrection_status.setObjectName("label_resurrection_status")
        self.label_resurrection_status.setWordWrap(True)
        form_layout.addRow("复活读条", self.label_resurrection_status)

        self._update_resurrection_label()
        self._update_sentry_auto_activate_label()
        self._update_rune_window_label()
        self._setup_posture_inputs()

    def _setup_posture_inputs(self):
        self.groupBox_posture = QtWidgets.QGroupBox(self)
        self.groupBox_posture.setObjectName("groupBox_posture")
        self.groupBox_posture.setTitle("V2.0.0 哨兵姿态")
        self.groupBox_posture.setGeometry(1020, 20, 280, 465)
        posture_layout = QtWidgets.QFormLayout(self.groupBox_posture)

        self.comboBox_sentry_posture = QtWidgets.QComboBox(self.groupBox_posture)
        for mode in range(1, 7):
            self.comboBox_sentry_posture.addItem(f"[{mode}] {POSTURE_NAMES[mode]}", mode)
        self.pushButton_force_posture = QtWidgets.QPushButton("强制设置", self.groupBox_posture)
        posture_select_layout = QtWidgets.QHBoxLayout()
        posture_select_layout.addWidget(self.comboBox_sentry_posture)
        posture_select_layout.addWidget(self.pushButton_force_posture)
        posture_layout.addRow("当前姿态", posture_select_layout)

        self.posture_normal_spinboxes = {}
        self.posture_enhanced_spinboxes = {}
        labels = {1: "进攻", 2: "防御", 3: "移动"}
        for base in (1, 2, 3):
            spinbox = self._create_posture_time_spinbox(180, 180)
            self.posture_normal_spinboxes[base] = spinbox
            posture_layout.addRow(f"普通{labels[base]}剩余", spinbox)
            spinbox.valueChanged.connect(
                lambda value, posture=base: self._on_posture_time_changed(
                    "normal", posture, value))

        for base in (1, 2, 3):
            spinbox = self._create_posture_time_spinbox(15, 15)
            self.posture_enhanced_spinboxes[base] = spinbox
            posture_layout.addRow(f"强化{labels[base]}剩余", spinbox)
            spinbox.valueChanged.connect(
                lambda value, posture=base: self._on_posture_time_changed(
                    "enhanced", posture, value))

        self.label_posture_cooldown = QtWidgets.QLabel(self.groupBox_posture)
        self.label_posture_result = QtWidgets.QLabel(self.groupBox_posture)
        self.label_posture_result.setWordWrap(True)
        posture_layout.addRow("切换冷却", self.label_posture_cooldown)
        posture_layout.addRow("最近结果", self.label_posture_result)

        self.pushButton_reset_posture = QtWidgets.QPushButton("重置 180/15", self.groupBox_posture)
        self.pushButton_expire_posture = QtWidgets.QPushButton("耗尽当前强化", self.groupBox_posture)
        posture_button_layout = QtWidgets.QHBoxLayout()
        posture_button_layout.addWidget(self.pushButton_reset_posture)
        posture_button_layout.addWidget(self.pushButton_expire_posture)
        posture_layout.addRow(posture_button_layout)

        self.pushButton_enhanced_attack_2s = QtWidgets.QPushButton(
            "场景：强化进攻剩余 2s", self.groupBox_posture)
        posture_layout.addRow(self.pushButton_enhanced_attack_2s)

        self.pushButton_force_posture.clicked.connect(self._on_force_posture_clicked)
        self.pushButton_reset_posture.clicked.connect(self._on_reset_posture_clicked)
        self.pushButton_expire_posture.clicked.connect(self._on_expire_posture_clicked)
        self.pushButton_enhanced_attack_2s.clicked.connect(
            self._on_enhanced_attack_2s_clicked)
        self._sync_posture_ui()

    def _setup_v2_game_hp_inputs(self):
        self.groupBox_v2_game_hp = QtWidgets.QGroupBox(self)
        self.groupBox_v2_game_hp.setObjectName("groupBox_v2_game_hp")
        self.groupBox_v2_game_hp.setTitle("V2.0.0 对局血量")
        self.groupBox_v2_game_hp.setGeometry(780, 360, 230, 345)
        layout = QtWidgets.QFormLayout(self.groupBox_v2_game_hp)

        self.spinBox_damage_difference = QtWidgets.QSpinBox(self.groupBox_v2_game_hp)
        self.spinBox_damage_difference.setRange(-32768, 32767)
        self.spinBox_enemy_outpost_hp = QtWidgets.QSpinBox(self.groupBox_v2_game_hp)
        self.spinBox_enemy_outpost_hp.setRange(0, 5000)
        self.spinBox_enemy_outpost_hp.setValue(1500)
        self.spinBox_enemy_base_hp = QtWidgets.QSpinBox(self.groupBox_v2_game_hp)
        self.spinBox_enemy_base_hp.setRange(0, 10000)
        self.spinBox_enemy_base_hp.setValue(5000)
        layout.addRow("伤害差", self.spinBox_damage_difference)
        layout.addRow("敌方前哨站", self.spinBox_enemy_outpost_hp)
        layout.addRow("敌方基地", self.spinBox_enemy_base_hp)

        self.spinBox_test_shooter_heat = QtWidgets.QSpinBox(self.groupBox_v2_game_hp)
        self.spinBox_test_shooter_heat.setRange(0, 1000)
        self.spinBox_test_shooter_heat.valueChanged.connect(
            lambda value: setattr(self, "shooter_17mm_heat", int(value)))
        layout.addRow("17mm 热量", self.spinBox_test_shooter_heat)

        self.pushButton_destroy_enemy_outpost = QtWidgets.QPushButton(
            "敌方前哨站归零", self.groupBox_v2_game_hp)
        self.pushButton_reset_enemy_hp = QtWidgets.QPushButton(
            "重置敌方建筑", self.groupBox_v2_game_hp)
        layout.addRow(self.pushButton_destroy_enemy_outpost)
        layout.addRow(self.pushButton_reset_enemy_hp)
        self.pushButton_heat_shot = QtWidgets.QPushButton("模拟射击：热量 +10", self.groupBox_v2_game_hp)
        self.pushButton_hurt_burst = QtWidgets.QPushButton("连续受击 3 次", self.groupBox_v2_game_hp)
        layout.addRow(self.pushButton_heat_shot)
        layout.addRow(self.pushButton_hurt_burst)
        self.pushButton_destroy_enemy_outpost.clicked.connect(
            lambda: self.spinBox_enemy_outpost_hp.setValue(0))
        self.pushButton_reset_enemy_hp.clicked.connect(self._reset_enemy_hp)
        self.pushButton_heat_shot.clicked.connect(self._simulate_heat_shot)
        self.pushButton_hurt_burst.clicked.connect(self._start_hurt_burst)

    def _create_posture_time_spinbox(self, maximum, value):
        spinbox = QtWidgets.QSpinBox(self.groupBox_posture)
        spinbox.setRange(0, maximum)
        spinbox.setSuffix(" s")
        spinbox.setValue(value)
        return spinbox
