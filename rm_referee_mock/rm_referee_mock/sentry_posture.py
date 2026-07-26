#!/usr/bin/env python3

"""V2.0.0 sentry posture state and protocol helpers."""

from time import monotonic

from rm_referee_mock.protocol import decode_sentry_command


POSTURE_NAMES = {
    0: "无效",
    1: "进攻",
    2: "防御",
    3: "移动",
    4: "强化进攻",
    5: "强化防御",
    6: "强化移动",
}


def base_posture(mode):
    mode = int(mode)
    return mode - 3 if mode in (4, 5, 6) else mode


def is_enhanced_posture(mode):
    return int(mode) in (4, 5, 6)


class SentryPostureState:
    NORMAL_DURATION_SECONDS = 180
    ENHANCED_DURATION_SECONDS = 15

    def __init__(self, cooldown_seconds=5.0, clock=monotonic):
        self.cooldown_seconds = float(cooldown_seconds)
        self._clock = clock
        self.reset()

    def reset(self):
        self.current_mode = 3
        self.normal_remaining = {
            1: self.NORMAL_DURATION_SECONDS,
            2: self.NORMAL_DURATION_SECONDS,
            3: self.NORMAL_DURATION_SECONDS,
        }
        self.enhanced_remaining = {
            1: self.ENHANCED_DURATION_SECONDS,
            2: self.ENHANCED_DURATION_SECONDS,
            3: self.ENHANCED_DURATION_SECONDS,
        }
        self.last_change_time = None
        self.last_result = "已重置：普通移动"

    def cooldown_remaining(self, now=None):
        if self.last_change_time is None:
            return 0.0
        now = self._clock() if now is None else float(now)
        return max(0.0, self.cooldown_seconds - (now - self.last_change_time))

    def request_mode(self, mode, now=None, bypass_cooldown=False):
        mode = int(mode)
        now = self._clock() if now is None else float(now)
        if mode < 1 or mode > 6:
            self.last_result = f"拒绝无效姿态 {mode}"
            return False, self.last_result

        if mode == self.current_mode:
            self.last_result = f"已处于{POSTURE_NAMES[mode]}"
            return True, self.last_result

        base = base_posture(mode)
        if is_enhanced_posture(mode) and self.enhanced_remaining[base] <= 0:
            self.last_result = f"拒绝{POSTURE_NAMES[mode]}：累计 15s 已耗尽"
            return False, self.last_result

        remaining_cooldown = self.cooldown_remaining(now)
        if remaining_cooldown > 0.0 and not bypass_cooldown:
            self.last_result = (
                f"拒绝 {POSTURE_NAMES[self.current_mode]}→{POSTURE_NAMES[mode]}："
                f"冷却剩余 {remaining_cooldown:.2f}s"
            )
            return False, self.last_result

        previous_mode = self.current_mode
        self.current_mode = mode
        self.last_change_time = now
        self.last_result = f"{POSTURE_NAMES[previous_mode]}→{POSTURE_NAMES[mode]}"
        return True, self.last_result

    def force_mode(self, mode, now=None):
        return self.request_mode(mode, now=now, bypass_cooldown=True)

    def set_normal_remaining(self, base, seconds):
        base = int(base)
        if base not in self.normal_remaining:
            raise ValueError(f"invalid base posture: {base}")
        self.normal_remaining[base] = max(
            0, min(self.NORMAL_DURATION_SECONDS, int(seconds)))

    def set_enhanced_remaining(self, base, seconds):
        base = int(base)
        if base not in self.enhanced_remaining:
            raise ValueError(f"invalid base posture: {base}")
        self.enhanced_remaining[base] = max(
            0, min(self.ENHANCED_DURATION_SECONDS, int(seconds)))

    def expire_current_enhanced(self):
        if not is_enhanced_posture(self.current_mode):
            self.last_result = "当前不是强化姿态"
            return False
        base = base_posture(self.current_mode)
        previous_mode = self.current_mode
        self.enhanced_remaining[base] = 0
        self.current_mode = base
        self.last_result = (
            f"{POSTURE_NAMES[previous_mode]}额度耗尽，自动回到{POSTURE_NAMES[base]}"
        )
        return True

    def tick(self, active=True):
        """Advance one rules second and return whether automatic fallback occurred."""
        if not active or self.current_mode < 1 or self.current_mode > 6:
            return False

        base = base_posture(self.current_mode)
        self.normal_remaining[base] = max(0, self.normal_remaining[base] - 1)

        if not is_enhanced_posture(self.current_mode):
            return False

        self.enhanced_remaining[base] = max(0, self.enhanced_remaining[base] - 1)
        if self.enhanced_remaining[base] > 0:
            return False

        previous_mode = self.current_mode
        self.current_mode = base
        self.last_result = (
            f"{POSTURE_NAMES[previous_mode]}额度耗尽，自动回到{POSTURE_NAMES[base]}"
        )
        return True

    def pack_sentry_info_3(self):
        value = 0
        value |= self.normal_remaining[1] & 0xFF
        value |= (self.normal_remaining[2] & 0xFF) << 8
        value |= (self.normal_remaining[3] & 0xFF) << 16
        value |= (self.enhanced_remaining[1] & 0xFF) << 32
        value |= (self.enhanced_remaining[2] & 0xFF) << 40
        value |= (self.enhanced_remaining[3] & 0xFF) << 48
        return value
