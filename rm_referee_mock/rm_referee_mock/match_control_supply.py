import math

from rm_referee_mock.rules import available_supply_projectile, timed_income_events


class MatchControlSupply:
    def set_auto_supply_points(self, points):
        cleaned_points = []
        for item in points:
            if len(item) != 3:
                continue
            name, x, y = item
            cleaned_points.append((str(name), float(x), float(y)))

        if cleaned_points:
            self.auto_supply_points = cleaned_points
            self._refresh_auto_supply_status()

    def update_auto_supply_pose(self, x, y, source=""):
        self.auto_supply_pose = (float(x), float(y), str(source))
        self._refresh_auto_supply_status()

    def _refresh_auto_supply_status(self):
        previous_detected = self.auto_supply_zone_detected
        previous_name = self.auto_supply_zone_name
        self.auto_supply_zone_detected = False
        self.auto_supply_zone_name = ""

        if self.auto_supply_pose is None or not self.auto_supply_points:
            return

        robot_x, robot_y, source = self.auto_supply_pose
        nearest_name = ""
        nearest_distance = None
        for name, point_x, point_y in self.auto_supply_points:
            distance = math.hypot(robot_x - point_x, robot_y - point_y)
            if nearest_distance is None or distance < nearest_distance:
                nearest_name = name
                nearest_distance = distance

        if nearest_distance is not None and nearest_distance <= self.SUPPLY_DETECT_RADIUS_M:
            self.auto_supply_zone_detected = True
            self.auto_supply_zone_name = nearest_name

        if (
            self.auto_supply_zone_detected != previous_detected
            or self.auto_supply_zone_name != previous_name
        ):
            state = "进入" if self.auto_supply_zone_detected else "离开"
            target = self.auto_supply_zone_name or previous_name or "补给区"
            print(f"[Supply] {state}{target}，定位来源={source or '-'}")

    def _manual_supply_zone_selected(self):
        supply_selected = self.checkBox_2.isChecked() if hasattr(self, "checkBox_2") else False
        rmul_supply_selected = self.checkBox_3.isChecked() if hasattr(self, "checkBox_3") else False
        return supply_selected or rmul_supply_selected

    def is_supply_zone_occupied(self):
        if self.comboBox_game_stage.currentIndex() != self.MATCH_STAGE_INDEX:
            return False
        return self._manual_supply_zone_selected() or self.auto_supply_zone_detected

    def get_rfid_status_value(self):
        rfid_status = 0
        rfid_status_2 = 0

        if hasattr(self, "checkBox_base_buff") and self.checkBox_base_buff.isChecked():
            rfid_status |= 1 << 0
        if hasattr(self, "comboBox_fortress_buff") and self.comboBox_fortress_buff.currentIndex() in (1, 3):
            rfid_status |= 1 << 17
        if hasattr(self, "comboBox_outpost_buff") and self.comboBox_outpost_buff.currentIndex() == 1:
            rfid_status |= 1 << 18
        if self.auto_supply_zone_detected or (hasattr(self, "checkBox_3") and self.checkBox_3.isChecked()):
            rfid_status |= 1 << 19
        if hasattr(self, "checkBox_2") and self.checkBox_2.isChecked():
            rfid_status |= 1 << 20

        return {
            "rfid_status": rfid_status,
            "rfid_status_2": rfid_status_2,
        }

    def _sync_gold_income(self, remain_seconds):
        if self.comboBox_game_stage.currentIndex() != self.MATCH_STAGE_INDEX or not self.spinBox_gold_coin:
            return

        if "initial" not in self.gold_income_claimed:
            current_gold = self.spinBox_gold_coin.value()
            if current_gold < self.GOLD_INITIAL_FLOOR:
                self.spinBox_gold_coin.setValue(self.GOLD_INITIAL_FLOOR)
                print(f"[Economy] 初始低保金币补足到 {self.GOLD_INITIAL_FLOOR}")
            self.gold_income_claimed.add("initial")

        for event_name, _, amount in timed_income_events(
                remain_seconds, self.gold_income_claimed, self.GOLD_TIMED_INCOME):
            self.spinBox_gold_coin.setValue(
                min(self.spinBox_gold_coin.maximum(), self.spinBox_gold_coin.value() + amount)
            )
            self.gold_income_claimed.add(event_name)
            print(f"[Economy] {event_name} 低保金币 +{amount}，当前 {self.spinBox_gold_coin.value()}")

    def _available_supply_projectile(self, remain_seconds):
        return available_supply_projectile(
            remain_seconds,
            self.DEFAULT_MATCH_REMAIN_SECONDS,
            self.SUPPLY_PROJECTILE_PER_MINUTE,
            self.SUPPLY_PROJECTILE_MAX_MINUTES,
        )

    def _claim_supply_projectile(self, remain_seconds):
        available = self._available_supply_projectile(remain_seconds)
        delta = max(0, available - self.supply_projectile_claimed)
        if delta <= 0:
            return

        self.spinBox_ammo.setValue(min(self.spinBox_ammo.maximum(), self.spinBox_ammo.value() + delta))
        self.supply_projectile_claimed += delta
        print(
            f"[Supply] 领取补给区累积发弹量 +{delta}，"
            f"已领取 {self.supply_projectile_claimed}，当前 17mm {self.spinBox_ammo.value()}"
        )

    def _tick_supply_zone_effects(self, remain_seconds):
        if not self.is_supply_zone_occupied():
            return

        current_hp = self.spinBox_hp_7.value()
        max_hp = self.spinBox_hp_7.maximum()
        if 0 < current_hp < max_hp:
            new_hp = min(max_hp, current_hp + self.SUPPLY_HEAL_HP_PER_SECOND)
            self.spinBox_hp_7.setValue(new_hp)
            print(f"[Supply] 补给区回血 +{new_hp - current_hp}，当前 HP {new_hp}/{max_hp}")

        self._claim_supply_projectile(remain_seconds)

    def confirm_projectile_exchange(self, exchange_target):
        exchange_target = int(exchange_target)
        current_exchange = self.spinBox_sentry_exchange_projectile.value()
        if exchange_target <= current_exchange:
            return True, f"补弹目标未增加，保持累计补弹 {current_exchange}"
        if exchange_target > 300:
            return False, f"补血点买弹上限为 300，收到目标 {exchange_target}"

        delta = exchange_target - current_exchange
        if delta % 10 != 0:
            return False, f"补给区买弹必须以 10 发为单位，收到增量 {delta}"

        remaining_gold_coin = self.spinBox_gold_coin.value() if self.spinBox_gold_coin else 0
        if remaining_gold_coin < delta:
            return False, f"剩余金币不足，当前 {remaining_gold_coin}，需要 {delta}"

        if self.spinBox_gold_coin:
            self.spinBox_gold_coin.setValue(max(0, remaining_gold_coin - delta))
        self.spinBox_ammo.setValue(min(self.spinBox_ammo.maximum(), self.spinBox_ammo.value() + delta))
        self.spinBox_sentry_exchange_projectile.setValue(exchange_target)
        return True, (
            f"补弹成功，累计补弹 {exchange_target}，"
            f"当前 17mm 允许发弹量 {self.spinBox_ammo.value()}"
        )
