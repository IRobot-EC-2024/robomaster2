from rm_referee_mock.rules import (
    available_supply_projectile,
    resurrection_required_seconds,
    rune_grants,
    timed_income_events,
)


def test_timed_income_is_idempotent_for_claimed_events():
    schedule = (("05:59", 359, 50), ("04:59", 299, 50))
    assert timed_income_events(300, set(), schedule) == [("05:59", 359, 50)]
    assert timed_income_events(299, {"05:59"}, schedule) == [("04:59", 299, 50)]


def test_supply_projectile_accumulates_by_completed_minutes():
    assert available_supply_projectile(420, 420, 100, 6) == 0
    assert available_supply_projectile(359, 420, 100, 6) == 100
    assert available_supply_projectile(0, 420, 100, 6) == 600


def test_resurrection_and_rune_schedule_boundaries():
    assert resurrection_required_seconds(420, 420, 0) == 10
    assert resurrection_required_seconds(419, 420, 0) == 10
    assert resurrection_required_seconds(420, 420, 2) == 50
    assert rune_grants(421, 420) == (1, 0)
    assert rune_grants(420, 420) == (0, 0)
    assert rune_grants(241, 240) == (0, 1)
