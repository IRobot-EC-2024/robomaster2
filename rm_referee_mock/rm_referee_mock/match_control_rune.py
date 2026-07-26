from rm_referee_mock.rules import rune_grants


class MatchControlRune:
    def _get_rune_combo(self, rune_name):
        return self.comboBox_small_rune if rune_name == "small" else self.comboBox_big_rune

    def _get_rune_label(self, rune_name):
        return "小能量机关" if rune_name == "small" else "大能量机关"

    def _update_rune_combo_text(self, rune_name):
        combo = self._get_rune_combo(rune_name)
        remaining = self.rune_window_timers[rune_name]
        active_text = f"激活中({remaining}s)" if remaining > 0 else "激活中"
        combo.setItemText(0, "未激活")
        combo.setItemText(1, active_text)
        combo.setItemText(2, "已激活")

    def _set_rune_status(self, rune_name, ui_index):
        combo = self._get_rune_combo(rune_name)
        changed = combo.currentIndex() != ui_index
        self._suppress_rune_status_change = True
        try:
            if changed:
                combo.setCurrentIndex(ui_index)
        finally:
            self._suppress_rune_status_change = False

        self._apply_rune_status_change(rune_name, ui_index, initiated_by_user=False)

    def _apply_rune_status_change(self, rune_name, ui_index, initiated_by_user):
        if ui_index == 1:
            if self.rune_window_timers[rune_name] <= 0:
                self.rune_window_timers[rune_name] = self.RUNE_ACTIVATING_WINDOW_SECONDS
                print(
                    f"[Rune] {self._get_rune_label(rune_name)}进入正在激活状态，"
                    f"开启{self.RUNE_ACTIVATING_WINDOW_SECONDS}s打符窗口"
                )
        else:
            had_timer = self.rune_window_timers[rune_name] > 0
            self.rune_window_timers[rune_name] = 0
            if ui_index == 2 and had_timer:
                print(f"[Rune] {self._get_rune_label(rune_name)}已被成功激活")
            elif ui_index == 0 and initiated_by_user and had_timer:
                print(f"[Rune] {self._get_rune_label(rune_name)}被手动重置为未激活")

        self._refresh_sentry_activate_flag()
        self._update_rune_combo_text(rune_name)
        self._update_rune_window_label()

    def _on_rune_status_changed(self, rune_name, ui_index):
        if self._suppress_rune_status_change:
            return
        self._apply_rune_status_change(rune_name, ui_index, initiated_by_user=True)

    def _update_rune_window_label(self):
        if not hasattr(self, "label_rune_window_status"):
            return

        parts = []
        for rune_name in ("small", "big"):
            combo = self._get_rune_combo(rune_name)
            remaining = self.rune_window_timers[rune_name]
            self._update_rune_combo_text(rune_name)
            if combo.currentIndex() == 1 and remaining > 0:
                parts.append(f"{'小' if rune_name == 'small' else '大'}{remaining}s")

        text = "打符窗: " + " ".join(parts) if parts else "打符窗: -"
        self.label_rune_window_status.setText(text)

    def _refresh_sentry_activate_flag(self):
        current_small_status = self.comboBox_small_rune.currentIndex()
        current_big_status = self.comboBox_big_rune.currentIndex()
        self.sentry_can_activate_flag = (
            (self.small_rune_chances > 0 and current_small_status == 0)
            or (self.big_rune_chances > 0 and current_big_status == 0)
        )
        self._update_sentry_auto_activate_label()

    def _update_sentry_auto_activate_label(self):
        if hasattr(self, "label_sentry_auto_activate"):
            text = "是" if self.sentry_can_activate_flag else "否"
            self.label_sentry_auto_activate.setText(f"自动可打符: {text}")

    def _tick_rune_windows(self):
        for rune_name in ("small", "big"):
            combo = self._get_rune_combo(rune_name)
            if combo.currentIndex() != 1:
                continue

            remaining = self.rune_window_timers[rune_name]
            if remaining <= 0:
                continue

            remaining -= 1
            self.rune_window_timers[rune_name] = remaining
            if remaining == 0:
                print(
                    f"[Timeout] {self._get_rune_label(rune_name)}20s打符窗口结束，"
                    "仍未成功激活，恢复为未激活"
                )
                self._set_rune_status(rune_name, 0)
                continue

        self._update_rune_window_label()

    def _check_rune_refresh(self, remain_seconds):
        if remain_seconds == self.last_remain_seconds:
            return
        previous_remain_seconds = self.last_remain_seconds
        self.last_remain_seconds = remain_seconds

        small_grants, large_grants = rune_grants(previous_remain_seconds, remain_seconds)
        if small_grants:
            self.small_rune_chances += small_grants
            print(f"[Rule] 时间 {remain_seconds}s: 获得1次小能量机关激活机会 (当前累积: {self.small_rune_chances})")
        if large_grants:
            self.big_rune_chances += large_grants
            print(f"[Rule] 时间 {remain_seconds}s: 获得1次大能量机关激活机会 (当前累积: {self.big_rune_chances})")
        self._refresh_sentry_activate_flag()

    def confirm_activation(self):
        ui_checked = False
        if hasattr(self, 'checkBox_can_activate_rune'):
            ui_checked = self.checkBox_can_activate_rune.isChecked()

        if not (self.sentry_can_activate_flag or ui_checked):
            print(">>> [Fail] 激活拒绝：无累积次数")
            return False

        activated_type = 0
        current_small_status = self.comboBox_small_rune.currentIndex()
        current_big_status = self.comboBox_big_rune.currentIndex()

        if current_small_status == 1 or current_big_status == 1:
            active_rune_name = "small" if current_small_status == 1 else "big"
            print(
                f">>> [Ignore] {self._get_rune_label(active_rune_name)}已处于正在激活窗口内，"
                "忽略重复激活请求"
            )
            return True

        remain_seconds = self._get_stage_remain_time()
        prefer_big_rune = remain_seconds <= 240

        if prefer_big_rune and self.big_rune_chances > 0 and current_big_status == 0:
            activated_type = 2
            self.big_rune_chances -= 1
            print(f">>> [Success] 消耗1次大符机会 (剩余: {self.big_rune_chances})")
        elif self.small_rune_chances > 0 and current_small_status == 0:
            activated_type = 1
            self.small_rune_chances -= 1
            print(f">>> [Success] 消耗1次小符机会 (剩余: {self.small_rune_chances})")
        elif self.big_rune_chances > 0 and current_big_status == 0:
            activated_type = 2
            self.big_rune_chances -= 1
            print(f">>> [Success] 消耗1次大符机会 (剩余: {self.big_rune_chances})")
        elif ui_checked:
            if current_small_status == 0:
                activated_type = 1
            elif current_big_status == 0:
                activated_type = 2
            print(">>> [Debug] UI强制激活")

        if activated_type == 1:
            self._set_rune_status("small", 1)
        elif activated_type == 2:
            self._set_rune_status("big", 1)

        if activated_type > 0:
            self._refresh_sentry_activate_flag()
            return True

        print(">>> [Fail] 虽然有权限，但没有可激活的目标 (可能都已激活)")
        return False
