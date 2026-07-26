import math

from rm_referee_mock.rules import resurrection_required_seconds


class MatchControlResurrection:
    def _round_half_up(self, value):
        return int(math.floor(value + 0.5))

    def _calculate_resurrection_required_seconds(self, remain_seconds):
        return resurrection_required_seconds(
            remain_seconds, self.DEFAULT_MATCH_REMAIN_SECONDS, self.buy_revive_count)

    def _reset_power_heat_after_death(self):
        self.shooter_17mm_heat = 0
        self.shooter_42mm_heat = 0
        self.buffer_energy = self.DEFAULT_BUFFER_ENERGY_LIMIT
        if hasattr(self, "spinBox_test_shooter_heat"):
            self.spinBox_test_shooter_heat.setValue(0)

    def _reset_resurrection_state(self, clear_buy_count=False):
        self.resurrection_active = False
        self.resurrection_required_seconds = 0
        self.resurrection_progress = 0
        if clear_buy_count:
            self.buy_revive_count = 0
        self.sentry_weak_active = False
        self.sentry_invincible_remaining_seconds = 0
        self.chassis_power_boost_remaining_seconds = 0
        if hasattr(self, "checkBox_sentry_can_free_revive"):
            self.checkBox_sentry_can_free_revive.setChecked(False)
        if hasattr(self, "checkBox_sentry_can_buy_revive"):
            self.checkBox_sentry_can_buy_revive.setChecked(False)
        if hasattr(self, "checkBox_sentry_is_disengaged"):
            self.checkBox_sentry_is_disengaged.setChecked(False)
        self._update_resurrection_label()

    def _start_resurrection(self):
        remain_seconds = self._get_stage_remain_time()
        self.resurrection_active = True
        self.resurrection_required_seconds = self._calculate_resurrection_required_seconds(remain_seconds)
        self.resurrection_progress = 0
        self.sentry_weak_active = False
        self.sentry_invincible_remaining_seconds = 0
        self.chassis_power_boost_remaining_seconds = 0
        self._reset_power_heat_after_death()
        self.checkBox_sentry_can_free_revive.setChecked(False)
        self.checkBox_sentry_is_disengaged.setChecked(True)
        self._refresh_buy_revive_permission()
        print(
            "[Resurrection] 哨兵战亡，复活读条开始: "
            f"remain={remain_seconds}s required={self.resurrection_required_seconds}s "
            f"buy_revive_count={self.buy_revive_count}"
        )
        self._update_resurrection_label()

    def _sync_resurrection_state(self):
        current_hp = self.spinBox_hp_7.value()
        if self._last_sentry_hp is None:
            self._last_sentry_hp = current_hp

        if current_hp <= 0 and not self.resurrection_active:
            self._start_resurrection()
        elif current_hp > 0 and self.resurrection_active:
            self._reset_resurrection_state(clear_buy_count=False)

        self._last_sentry_hp = current_hp
        if current_hp <= 0 and self.resurrection_active:
            self._refresh_buy_revive_permission()

    def _resurrection_progress_step(self):
        in_supply_buff = self.is_supply_zone_occupied()
        base_low_hp = self.spinBox_hp_base.value() < 2000
        return 4 if in_supply_buff or base_low_hp else 1

    def _tick_resurrection(self):
        if not self.resurrection_active or self.spinBox_hp_7.value() > 0:
            self._tick_post_revive_effects()
            return

        if self.resurrection_required_seconds <= 0:
            return

        if self.resurrection_progress < self.resurrection_required_seconds:
            self.resurrection_progress = min(
                self.resurrection_required_seconds,
                self.resurrection_progress + self._resurrection_progress_step())

        if self.resurrection_progress >= self.resurrection_required_seconds:
            self.checkBox_sentry_can_free_revive.setChecked(True)

        self._refresh_buy_revive_permission()
        self._update_resurrection_label()

    def _tick_post_revive_effects(self):
        if self.sentry_weak_active and self._detect_weak_clear_card():
            self.sentry_weak_active = False
            elapsed_invincible_seconds = 30 - self.sentry_invincible_remaining_seconds
            if elapsed_invincible_seconds >= 10:
                self.sentry_invincible_remaining_seconds = 0
            else:
                self.sentry_invincible_remaining_seconds = 10 - elapsed_invincible_seconds
            print("[Resurrection] 检测到可占领交互模块卡，解除虚弱状态")

        if self.sentry_invincible_remaining_seconds > 0:
            self.sentry_invincible_remaining_seconds -= 1
        if self.chassis_power_boost_remaining_seconds > 0:
            self.chassis_power_boost_remaining_seconds -= 1
        self._update_resurrection_label()

    def _detect_weak_clear_card(self):
        in_supply_buff = self.is_supply_zone_occupied()
        base_buff_detected = self.checkBox_base_buff.isChecked() if hasattr(self, "checkBox_base_buff") else False
        outpost_buff_detected = (
            self.comboBox_outpost_buff.currentIndex() != 0
            if hasattr(self, "comboBox_outpost_buff")
            else False
        )
        return in_supply_buff or base_buff_detected or outpost_buff_detected

    def _refresh_buy_revive_permission(self):
        revive_cost = self.spinBox_sentry_buy_revive_cost.value()
        remaining_gold_coin = self.spinBox_gold_coin.value() if self.spinBox_gold_coin else 0
        can_buy = self.spinBox_hp_7.value() <= 0 and remaining_gold_coin >= revive_cost
        self.checkBox_sentry_can_buy_revive.setChecked(can_buy)

    def _restore_sentry_hp_ratio(self, ratio):
        max_hp = self.spinBox_hp_7.maximum()
        restored_hp = max(1, self._round_half_up(max_hp * ratio))
        self.spinBox_hp_7.setValue(min(max_hp, restored_hp))

    def _restore_sentry_hp_full(self):
        self.spinBox_hp_7.setValue(self.spinBox_hp_7.maximum())

    def _current_chassis_power_limit(self):
        if self.chassis_power_boost_remaining_seconds <= 0:
            return self.DEFAULT_CHASSIS_POWER_LIMIT
        return min(200, self.DEFAULT_CHASSIS_POWER_LIMIT * 2)

    def _update_resurrection_label(self):
        if not hasattr(self, "label_resurrection_status"):
            return

        if self.resurrection_active and self.spinBox_hp_7.value() <= 0:
            self.label_resurrection_status.setText(
                f"{self.resurrection_progress}/{self.resurrection_required_seconds}s "
                f"金币复活{self.buy_revive_count}次"
            )
            return

        effects = []
        if self.sentry_invincible_remaining_seconds > 0:
            effects.append(f"无敌{self.sentry_invincible_remaining_seconds}s")
        if self.sentry_weak_active:
            effects.append("虚弱")
        if self.chassis_power_boost_remaining_seconds > 0:
            effects.append(f"功率提升{self.chassis_power_boost_remaining_seconds}s")
        suffix = " ".join(effects) if effects else "-"
        self.label_resurrection_status.setText(f"{suffix} 金币复活{self.buy_revive_count}次")

    def confirm_free_revive(self):
        if self.spinBox_hp_7.value() > 0:
            return False, "哨兵未战亡，免费复活无效"
        if not self.checkBox_sentry_can_free_revive.isChecked():
            return False, (
                "当前不可免费复活，读条 "
                f"{self.resurrection_progress}/{self.resurrection_required_seconds}s"
            )

        self._restore_sentry_hp_ratio(0.10)
        self.checkBox_sentry_can_free_revive.setChecked(False)
        self.checkBox_sentry_can_buy_revive.setChecked(False)
        self.checkBox_sentry_is_disengaged.setChecked(False)
        self.resurrection_active = False
        self.sentry_invincible_remaining_seconds = 30
        self.sentry_weak_active = True
        self._update_resurrection_label()
        return True, f"免费复活成功，哨兵血量恢复至 {self.spinBox_hp_7.value()}"

    def confirm_buy_revive(self):
        if self.spinBox_hp_7.value() > 0:
            return False, "哨兵未战亡，金币复活无效"
        self._refresh_buy_revive_permission()
        if not self.checkBox_sentry_can_buy_revive.isChecked():
            return False, "当前不可金币复活"

        revive_cost = self.spinBox_sentry_buy_revive_cost.value()
        remaining_gold_coin = self.spinBox_gold_coin.value() if self.spinBox_gold_coin else 0
        if remaining_gold_coin < revive_cost:
            return False, f"剩余金币不足，当前 {remaining_gold_coin}，需要 {revive_cost}"

        if self.spinBox_gold_coin:
            self.spinBox_gold_coin.setValue(max(0, remaining_gold_coin - revive_cost))
        self._restore_sentry_hp_full()
        self.buy_revive_count += 1
        self.checkBox_sentry_can_buy_revive.setChecked(False)
        self.checkBox_sentry_can_free_revive.setChecked(False)
        self.checkBox_sentry_is_disengaged.setChecked(False)
        self.resurrection_active = False
        self.sentry_invincible_remaining_seconds = 3
        self.sentry_weak_active = False
        self.chassis_power_boost_remaining_seconds = 4
        self._update_resurrection_label()
        return True, f"金币复活成功，哨兵血量恢复至 {self.spinBox_hp_7.value()}"
