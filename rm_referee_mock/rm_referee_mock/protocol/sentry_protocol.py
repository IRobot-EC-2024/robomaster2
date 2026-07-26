"""Pure V2.0.0 sentry protocol conversions.

This module intentionally has no Qt or ROS dependencies, so bit layouts and
ordering rules can be unit-tested without starting rqt.
"""


def decode_sentry_command(value):
    """Decode the 32-bit 0x0120 sentry command payload."""
    value = int(value) & 0xFFFFFFFF
    return {
        "confirm_free_revive": value & 0x01,
        "confirm_buy_revive": (value >> 1) & 0x01,
        "exchange_projectile": (value >> 2) & 0x07FF,
        "remote_projectile_exchange_count": (value >> 13) & 0x0F,
        "remote_hp_exchange_count": (value >> 17) & 0x0F,
        "posture": (value >> 21) & 0x07,
        "activate_rune": (value >> 24) & 0x01,
        "raw": value,
    }


def truncate_sentry_command(command, current):
    """Apply the protocol's low-to-high-field processing rule.

    When a cumulative field is invalid, that field and every following field
    are cleared. ``current`` contains the last accepted cumulative counters.
    """
    result = dict(command)

    def clear_fields(fields, reason):
        for field in fields:
            result[field] = 0
        return result, reason

    current_exchange = int(current.get("exchange_projectile", 0))
    requested_exchange = int(result.get("exchange_projectile", 0))
    if requested_exchange < current_exchange:
        return clear_fields(
            ("exchange_projectile", "remote_projectile_exchange_count",
             "remote_hp_exchange_count", "posture", "activate_rune"),
            f"补血点补弹累计值回退，当前已成功兑换 {current_exchange}，本次请求 {requested_exchange}",
        )

    for field, label in (
        ("remote_projectile_exchange_count", "远程补弹请求次数"),
        ("remote_hp_exchange_count", "远程回血请求次数"),
    ):
        current_value = int(current.get(field, 0))
        requested_value = int(result.get(field, 0))
        trailing = (
            ("remote_projectile_exchange_count", "remote_hp_exchange_count", "posture", "activate_rune")
            if field == "remote_projectile_exchange_count"
            else ("remote_hp_exchange_count", "posture", "activate_rune")
        )
        if requested_value < current_value:
            return clear_fields(
                trailing, f"{label}回退，当前 {current_value}，本次请求 {requested_value}")
        if requested_value > current_value + 1:
            return clear_fields(
                trailing, f"{label}跳变，当前 {current_value}，本次请求 {requested_value}")

    return result, ""


def pack_sentry_info(status):
    """Pack a SentryInfo state mapping into the three protocol fields."""
    info = int(status.get("exchange_projectile", 0)) & 0x07FF
    info |= (int(status.get("remote_projectile_exchange_count", 0)) & 0x0F) << 11
    info |= (int(status.get("remote_hp_exchange_count", 0)) & 0x0F) << 15
    info |= (int(bool(status.get("can_free_revive", False))) & 0x01) << 19
    info |= (int(bool(status.get("can_buy_revive", False))) & 0x01) << 20
    info |= (int(status.get("buy_revive_cost", 0)) & 0x03FF) << 21

    info_2 = int(bool(status.get("is_disengaged", False))) & 0x01
    info_2 |= (int(status.get("team_projectile_exchange_remaining", 0)) & 0x07FF) << 1
    info_2 |= (int(status.get("base_posture", 3)) & 0x03) << 12
    info_2 |= (int(bool(status.get("can_activate", False))) & 0x01) << 14
    info_2 |= (int(bool(status.get("enhanced", False))) & 0x01) << 15

    return info, info_2, int(status.get("sentry_info_3", 0))
