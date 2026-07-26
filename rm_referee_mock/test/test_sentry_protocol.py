from rm_referee_mock.protocol import pack_sentry_info, truncate_sentry_command


def test_pack_sentry_info_keeps_protocol_bit_layout():
    info, info_2, info_3 = pack_sentry_info({
        "exchange_projectile": 7,
        "remote_projectile_exchange_count": 2,
        "remote_hp_exchange_count": 3,
        "can_free_revive": True,
        "can_buy_revive": True,
        "buy_revive_cost": 100,
        "base_posture": 2,
        "enhanced": True,
        "can_activate": True,
        "sentry_info_3": 42,
    })
    assert info & 0x07FF == 7
    assert (info >> 11) & 0x0F == 2
    assert (info >> 15) & 0x0F == 3
    assert (info_2 >> 12) & 0x03 == 2
    assert (info_2 >> 14) & 0x01 == 1
    assert (info_2 >> 15) & 0x01 == 1
    assert info_3 == 42


def test_invalid_counter_clears_it_and_all_following_fields():
    command = {
        "exchange_projectile": 9,
        "remote_projectile_exchange_count": 4,
        "remote_hp_exchange_count": 2,
        "posture": 3,
        "activate_rune": 1,
    }
    result, reason = truncate_sentry_command(command, {
        "exchange_projectile": 9,
        "remote_projectile_exchange_count": 2,
        "remote_hp_exchange_count": 2,
    })
    assert result["exchange_projectile"] == 9
    assert result["remote_projectile_exchange_count"] == 0
    assert result["remote_hp_exchange_count"] == 0
    assert result["posture"] == 0
    assert result["activate_rune"] == 0
    assert "跳变" in reason
