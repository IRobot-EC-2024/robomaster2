"""Deterministic calculations used by the match-control simulation."""

import math


def timed_income_events(remain_seconds, claimed, schedule):
    """Return newly reached income events without mutating caller state."""
    return [event for event in schedule
            if remain_seconds <= event[1] and event[0] not in claimed]


def available_supply_projectile(
        remain_seconds, match_seconds, per_minute, maximum_minutes):
    bounded = max(0, min(int(match_seconds), int(remain_seconds)))
    elapsed_minutes = max(0, (int(match_seconds) - bounded) // 60)
    return min(int(maximum_minutes), elapsed_minutes) * int(per_minute)


def resurrection_required_seconds(remain_seconds, match_seconds, buy_revive_count):
    bounded = min(int(match_seconds), max(0, int(remain_seconds)))
    seconds = 10 + ((int(match_seconds) - bounded) / 10.0) + 20 * int(buy_revive_count)
    return int(math.floor(seconds + 0.5))


def rune_grants(last_remain_seconds, remain_seconds):
    """Return ``(small, large)`` grant counts for a newly observed second."""
    remain_seconds = int(remain_seconds)
    if remain_seconds == last_remain_seconds:
        return 0, 0
    return int(remain_seconds in (420, 330)), int(remain_seconds in (240, 165, 90))
