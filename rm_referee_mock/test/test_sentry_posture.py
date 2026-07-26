#!/usr/bin/env python3

from rm_referee_mock.sentry_posture import (
    SentryPostureState,
    decode_sentry_command,
)


def test_v200_command_uses_three_posture_bits_and_bit24_for_rune():
    enhanced_attack = decode_sentry_command(4 << 21)
    assert enhanced_attack["posture"] == 4
    assert enhanced_attack["activate_rune"] == 0

    enhanced_move_and_rune = decode_sentry_command((6 << 21) | (1 << 24))
    assert enhanced_move_and_rune["posture"] == 6
    assert enhanced_move_and_rune["activate_rune"] == 1


def test_enhanced_timer_is_independent_and_falls_back_to_matching_posture():
    state = SentryPostureState(clock=lambda: 0.0)
    accepted, _ = state.request_mode(5, now=0.0)
    assert accepted

    for _ in range(15):
        state.tick()

    assert state.current_mode == 2
    assert state.enhanced_remaining == {1: 15, 2: 0, 3: 15}
    # 强化防御也计入普通防御姿态的累计 180s。
    assert state.normal_remaining == {1: 180, 2: 165, 3: 180}


def test_reentering_enhanced_posture_continues_consuming_same_budget():
    state = SentryPostureState(clock=lambda: 0.0)
    assert state.request_mode(4, now=0.0)[0]
    for _ in range(5):
        state.tick()
    assert state.enhanced_remaining[1] == 10

    assert state.request_mode(3, now=5.0)[0]
    assert state.request_mode(4, now=10.0)[0]
    assert state.enhanced_remaining[1] == 10


def test_expired_enhanced_posture_is_semantically_rejected():
    state = SentryPostureState(clock=lambda: 0.0)
    state.set_enhanced_remaining(3, 0)
    accepted, message = state.request_mode(6, now=10.0)
    assert not accepted
    assert state.current_mode == 3
    assert "耗尽" in message


def test_cooldown_does_not_block_server_side_automatic_fallback():
    state = SentryPostureState(clock=lambda: 0.0)
    state.set_enhanced_remaining(1, 1)
    assert state.request_mode(4, now=0.0)[0]
    assert state.tick()
    assert state.current_mode == 1


def test_switch_request_is_rejected_during_five_second_cooldown():
    state = SentryPostureState(clock=lambda: 0.0)
    assert state.request_mode(1, now=0.0)[0]
    accepted, message = state.request_mode(2, now=4.9)
    assert not accepted
    assert state.current_mode == 1
    assert "冷却" in message

    assert state.request_mode(2, now=5.0)[0]


def test_sentry_info_3_layout_contains_all_six_windows():
    state = SentryPostureState(clock=lambda: 0.0)
    state.set_normal_remaining(1, 101)
    state.set_normal_remaining(2, 102)
    state.set_normal_remaining(3, 103)
    state.set_enhanced_remaining(1, 11)
    state.set_enhanced_remaining(2, 12)
    state.set_enhanced_remaining(3, 13)

    packed = state.pack_sentry_info_3()
    assert packed & 0xFF == 101
    assert (packed >> 8) & 0xFF == 102
    assert (packed >> 16) & 0xFF == 103
    assert (packed >> 32) & 0xFF == 11
    assert (packed >> 40) & 0xFF == 12
    assert (packed >> 48) & 0xFF == 13
