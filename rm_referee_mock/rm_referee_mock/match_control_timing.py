class MatchControlTiming:
    def _is_rmul_game_type(self):
        return self.comboBox_game_type.currentIndex() in self.RMUL_GAME_TYPES

    def _reset_match_timer(self):
        self.lineEdit_time.set_confirmed_text(self._format_seconds(self.DEFAULT_MATCH_REMAIN_SECONDS))
        self.stage_countdown_remaining = 0
        self._update_stage_countdown_display()

    def _reset_match_runtime_state(self):
        self.sentry_can_activate_flag = False
        self.small_rune_chances = 0
        self.big_rune_chances = 0
        self.last_remain_seconds = -1
        self.rune_window_timers = {"small": 0, "big": 0}
        self._set_rune_status("small", 0)
        self._set_rune_status("big", 0)
        self.supply_projectile_claimed = 0
        self.gold_income_claimed = set()
        self.sentry_posture.reset()
        if hasattr(self, "spinBox_damage_difference"):
            self.spinBox_damage_difference.setValue(0)
            self._reset_enemy_hp()
        self._reset_resurrection_state(clear_buy_count=True)
        if hasattr(self, "checkBox_can_activate_rune"):
            self.checkBox_can_activate_rune.setChecked(False)
        self._update_sentry_auto_activate_label()
        self._update_rune_window_label()
        self._sync_posture_ui()

    def _on_game_stage_changed(self, stage_index):
        if stage_index in self.PRE_MATCH_STAGE_DURATIONS:
            self.stage_countdown_remaining = self.PRE_MATCH_STAGE_DURATIONS[stage_index]
            self._update_stage_countdown_display()
            self._set_countdown_running(True)
            return

        self.stage_countdown_remaining = 0
        self._update_stage_countdown_display()
        if stage_index in (0, 1):
            self._reset_match_timer()
            self._reset_match_runtime_state()
            self._set_countdown_running(False)
            return

        if stage_index == self.MATCH_STAGE_INDEX:
            remain_seconds = self._parse_time_to_seconds()
            self._sync_gold_income(remain_seconds)
            self._check_rune_refresh(remain_seconds)
            self._set_countdown_running(True)
            return

        if stage_index == self.FINISHED_STAGE_INDEX:
            self._set_countdown_running(False)

    def _update_stage_countdown_display(self):
        if not hasattr(self, "label_stage_countdown"):
            return
        if self.stage_countdown_remaining > 0:
            self.label_stage_countdown.setText(
                f"预倒计时: {self._format_seconds(self.stage_countdown_remaining)}"
            )
        else:
            self.label_stage_countdown.clear()

    def _set_countdown_running(self, running):
        self.pushButton_playpause.setText("⏸" if running else "▶")
        self.lineEdit_time.setReadOnly(running)
        if running:
            self.countdown_timer.start(1000)
        else:
            self.countdown_timer.stop()

    def _tick_stage_countdown(self):
        stage_index = self.comboBox_game_stage.currentIndex()
        if self.stage_countdown_remaining <= 0:
            self.stage_countdown_remaining = self.PRE_MATCH_STAGE_DURATIONS[stage_index]

        self.stage_countdown_remaining -= 1
        self._update_stage_countdown_display()
        if self.stage_countdown_remaining > 0:
            return

        next_stage = 3 if stage_index == 2 else self.MATCH_STAGE_INDEX
        self.comboBox_game_stage.setCurrentIndex(next_stage)

    def _tick_match_countdown(self):
        total_seconds = self._parse_time_to_seconds()
        if total_seconds <= 0:
            if self.comboBox_game_stage.currentIndex() == self.MATCH_STAGE_INDEX:
                self.comboBox_game_stage.setCurrentIndex(self.FINISHED_STAGE_INDEX)
            self._set_countdown_running(False)
            return

        total_seconds -= 1
        self.lineEdit_time.set_confirmed_text(self._format_seconds(total_seconds))
        self._sync_gold_income(total_seconds)
        self._tick_supply_zone_effects(total_seconds)
        self._check_rune_refresh(total_seconds)

        if total_seconds == 0:
            if self.comboBox_game_stage.currentIndex() == self.MATCH_STAGE_INDEX:
                self.comboBox_game_stage.setCurrentIndex(self.FINISHED_STAGE_INDEX)
            self._set_countdown_running(False)

    def _format_seconds(self, total_seconds):
        minutes, seconds = divmod(max(0, total_seconds), 60)
        return f"{minutes}:{seconds:02d}"

    def _get_stage_remain_time(self):
        stage_index = self.comboBox_game_stage.currentIndex()
        if stage_index in self.PRE_MATCH_STAGE_DURATIONS and self.stage_countdown_remaining > 0:
            return self.stage_countdown_remaining
        return self._parse_time_to_seconds()

    def on_play_pause_clicked(self):
        if self.pushButton_playpause.text() == "▶":
            stage_index = self.comboBox_game_stage.currentIndex()
            if stage_index in self.PRE_MATCH_STAGE_DURATIONS and self.stage_countdown_remaining <= 0:
                self.stage_countdown_remaining = self.PRE_MATCH_STAGE_DURATIONS[stage_index]
                self._update_stage_countdown_display()
            if stage_index == self.MATCH_STAGE_INDEX:
                self._check_rune_refresh(self._parse_time_to_seconds())
            self._set_countdown_running(True)
        else:
            self._set_countdown_running(False)

    def update_time(self):
        self._sync_resurrection_state()
        if self.comboBox_game_stage.currentIndex() in self.PRE_MATCH_STAGE_DURATIONS:
            self._tick_stage_countdown()
            return

        self._tick_rune_windows()
        self._tick_sentry_posture()
        self._tick_resurrection()
        self._tick_match_countdown()

    def _parse_time_to_seconds(self, time_str=None):
        if time_str is None:
            time_str = self.lineEdit_time.get_confirmed_text()
        try:
            parts = time_str.strip().split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
        except (ValueError, IndexError):
            pass
        return 0

    def get_topic_prefix(self):
        prefix = self.lineEdit_topic_prefix.get_confirmed_text()
        if prefix and not prefix.startswith("/"):
            prefix = "/" + prefix
        if prefix.endswith("/"):
            prefix = prefix.rstrip("/")
        return prefix if prefix else ""
