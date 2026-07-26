from PyQt5.QtCore import QTimer

from rm_referee_mock.sentry_posture import POSTURE_NAMES


class MatchControlPosture:
    def _on_posture_time_changed(self, timer_type, base, value):
        if self._suppress_posture_ui_change:
            return
        if timer_type == "normal":
            self.sentry_posture.set_normal_remaining(base, value)
        else:
            self.sentry_posture.set_enhanced_remaining(base, value)
            if value == 0 and self.sentry_posture.current_mode == base + 3:
                self.sentry_posture.expire_current_enhanced()
        self._sync_posture_ui()

    def _sync_posture_ui(self):
        if not hasattr(self, "comboBox_sentry_posture"):
            return
        self._suppress_posture_ui_change = True
        try:
            self.comboBox_sentry_posture.setCurrentIndex(
                max(0, self.sentry_posture.current_mode - 1))
            for base, spinbox in self.posture_normal_spinboxes.items():
                spinbox.setValue(self.sentry_posture.normal_remaining[base])
            for base, spinbox in self.posture_enhanced_spinboxes.items():
                spinbox.setValue(self.sentry_posture.enhanced_remaining[base])
        finally:
            self._suppress_posture_ui_change = False

        remaining = self.sentry_posture.cooldown_remaining()
        self.label_posture_cooldown.setText(
            f"{remaining:.1f}s" if remaining > 0.0 else "就绪")
        self.label_posture_result.setText(self.sentry_posture.last_result)
        self.label_sentry_mode.setText(
            f"姿态: {POSTURE_NAMES[self.sentry_posture.current_mode]}")

    def _on_force_posture_clicked(self):
        mode = int(self.comboBox_sentry_posture.currentData())
        accepted, message = self.sentry_posture.force_mode(mode)
        print(f"[Posture-Debug] {'成功' if accepted else '拒绝'}: {message}")
        self._sync_posture_ui()

    def _on_reset_posture_clicked(self):
        self.sentry_posture.reset()
        print("[Posture-Debug] 已重置姿态和六个剩余时间")
        self._sync_posture_ui()

    def _on_expire_posture_clicked(self):
        changed = self.sentry_posture.expire_current_enhanced()
        print(f"[Posture-Debug] {self.sentry_posture.last_result}")
        if changed:
            self.update_sentry_echo(self.sentry_posture.current_mode)
        self._sync_posture_ui()

    def _on_enhanced_attack_2s_clicked(self):
        self.sentry_posture.set_enhanced_remaining(1, 2)
        self.sentry_posture.force_mode(4)
        print("[Posture-Debug] 场景已设置：强化进攻剩余 2s")
        self._sync_posture_ui()

    def request_sentry_posture(self, mode):
        accepted, message = self.sentry_posture.request_mode(mode)
        if accepted:
            self.update_sentry_echo(self.sentry_posture.current_mode)
        self._sync_posture_ui()
        return accepted, message

    def _tick_sentry_posture(self):
        active = (
            self.comboBox_game_stage.currentIndex() == self.MATCH_STAGE_INDEX
            and self.spinBox_hp_7.value() > 0
        )
        fallback = self.sentry_posture.tick(active=active)
        if fallback:
            print(f"[Posture-Timeout] {self.sentry_posture.last_result}")
            self.update_sentry_echo(self.sentry_posture.current_mode)
        self._sync_posture_ui()

    def update_sentry_echo(self, mode):
        if hasattr(self, 'label_sentry_mode'):
            txt = POSTURE_NAMES.get(mode, str(mode))
            self.label_sentry_mode.setText(f"姿态: {txt}")
            self.label_sentry_mode.setStyleSheet("color: red; font-weight: bold;")
            QTimer.singleShot(
                500,
                lambda: self.label_sentry_mode.setStyleSheet("color: blue; font-weight: bold;"))
