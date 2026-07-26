class MatchControlStatus:
    def get_event_data_value(self):
        def map_rune_status(ui_index):
            if ui_index == 0:
                return 0
            if ui_index == 1:
                return 2
            if ui_index == 2:
                return 1
            return 0

        event_val = 0
        auto_supply = (
            self.auto_supply_zone_detected
            and self.comboBox_game_stage.currentIndex() == self.MATCH_STAGE_INDEX
        )

        event_val |= int(self.checkBox_2.isChecked() or auto_supply) << 0
        if self._is_rmul_game_type():
            event_val |= int(self.checkBox_3.isChecked() or auto_supply) << 2

        event_val |= (map_rune_status(self.comboBox_small_rune.currentIndex()) & 0x03) << 3
        event_val |= (map_rune_status(self.comboBox_big_rune.currentIndex()) & 0x03) << 5
        event_val |= (self.comboBox_central_highland.currentIndex() & 0x03) << 7
        event_val |= int(self.checkBox_4.isChecked()) << 9

        dart_hit_time = min(
            420,
            max(0, self._parse_time_to_seconds(self.lineEdit_dart_time.get_confirmed_text())))
        event_val |= (dart_hit_time & 0x01FF) << 11
        event_val |= (self.comboBox_dart_target.currentIndex() & 0x07) << 20

        if self._is_rmul_game_type():
            event_val |= (self.comboBox_central_buff.currentIndex() & 0x03) << 23
        event_val |= (self.comboBox_fortress_buff.currentIndex() & 0x03) << 25
        event_val |= (self.comboBox_outpost_buff.currentIndex() & 0x03) << 27
        event_val |= int(self.checkBox_base_buff.isChecked()) << 29

        return event_val

    def get_game_status(self):
        self._sync_resurrection_state()
        sentry_info_status = self.get_sentry_info_status()
        status = {
            "game_type": self.comboBox_game_type.currentIndex(),
            "game_progress": self.comboBox_game_stage.currentIndex(),
            "stage_remain_time": self._get_stage_remain_time(),
            "robot_hp": {
                "hero": self.spinBox_hp_1.value(),
                "engineer": self.spinBox_hp_2.value(),
                "infantry_3": self.spinBox_hp_3.value(),
                "infantry_4": self.spinBox_hp_4.value(),
                "sentry": self.spinBox_hp_7.value(),
                "ally_outpost": self.spinBox_hp_outpost.value(),
                "ally_base": self.spinBox_hp_base.value(),
                "damage_difference": self.spinBox_damage_difference.value(),
                "enemy_outpost": self.spinBox_enemy_outpost_hp.value(),
                "enemy_base": self.spinBox_enemy_base_hp.value(),
            },
            "robot_status": {
                "id": int(self.comboBox_robot_id.currentData()),
                "current_hp": self.spinBox_hp_7.value(),
                "max_hp": self.spinBox_hp_7.maximum(),
                "ammo": self.spinBox_ammo.value(),
                "chassis_power_limit": self._current_chassis_power_limit(),
                "shooter_output": self._current_shooter_output(),
            },
            "projectile_allowance": {
                "projectile_allowance_17mm": self.spinBox_ammo.value(),
                "projectile_allowance_42mm": self.spinBox_ammo_42mm.value() if self.spinBox_ammo_42mm else 0,
                "remaining_gold_coin": self.spinBox_gold_coin.value() if self.spinBox_gold_coin else 0,
                "projectile_allowance_fortress": self.spinBox_ammo_fortress.value()
                if self.spinBox_ammo_fortress else 0,
            },
            "event_data": self.get_event_data_value(),
            "rfid_status": self.get_rfid_status_value(),
            "hurt_data": {
                "armor_id": self.current_hurt_armor_id if self.trigger_hurt else 0,
                "trigger": self.trigger_hurt
            },
            "sentry_can_activate": sentry_info_status["can_activate"],
            "sentry_info": sentry_info_status,
            "power_heat_data": {
                "buffer_energy": self.buffer_energy,
                "shooter_17mm_1_barrel_heat": self.shooter_17mm_heat,
                "shooter_42mm_barrel_heat": self.shooter_42mm_heat,
            },
        }
        if self.trigger_hurt:
            self.trigger_hurt = False

        return status

    def _current_shooter_output(self):
        manual_enabled = (
            self.checkBox_shooter_output.isChecked()
            if hasattr(self, "checkBox_shooter_output")
            else True
        )
        return manual_enabled and not self.sentry_weak_active

    def get_sentry_info_status(self):
        manual_can_activate = (
            self.checkBox_can_activate_rune.isChecked()
            if hasattr(self, "checkBox_can_activate_rune")
            else False
        )
        return {
            "exchange_projectile": self.spinBox_sentry_exchange_projectile.value(),
            "remote_projectile_exchange_count": self.spinBox_sentry_remote_projectile_exchange.value(),
            "remote_hp_exchange_count": self.spinBox_sentry_remote_hp_exchange.value(),
            "can_free_revive": self.checkBox_sentry_can_free_revive.isChecked(),
            "can_buy_revive": self.checkBox_sentry_can_buy_revive.isChecked(),
            "buy_revive_cost": self.spinBox_sentry_buy_revive_cost.value(),
            "is_disengaged": self.checkBox_sentry_is_disengaged.isChecked(),
            "team_projectile_exchange_remaining": self.spinBox_sentry_team_projectile_exchange.value(),
            "can_activate": self.sentry_can_activate_flag or manual_can_activate,
            "current_mode": self.sentry_posture.current_mode,
            "base_posture": (
                self.sentry_posture.current_mode - 3
                if self.sentry_posture.current_mode >= 4
                else self.sentry_posture.current_mode
            ),
            "enhanced": self.sentry_posture.current_mode >= 4,
            "posture_remaining": dict(self.sentry_posture.normal_remaining),
            "enhanced_posture_remaining": dict(self.sentry_posture.enhanced_remaining),
            "sentry_info_3": self.sentry_posture.pack_sentry_info_3(),
        }
