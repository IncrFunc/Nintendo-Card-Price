import random

from nsg_price.automation import pick_time_in_window, planned_publish_times_for_date


def test_pick_time_in_window_is_inclusive_and_deterministic():
    assert pick_time_in_window("10:00-10:10", rng=random.Random(0)) == "10:06"


def test_planned_publish_times_keeps_each_window_key():
    planned = planned_publish_times_for_date(
        ["10:00-10:10", "16:00-16:10"],
        date="2026-06-15",
        rng=random.Random(1),
    )

    assert set(planned) == {"10:00-10:10", "16:00-16:10"}
    assert "10:00" <= planned["10:00-10:10"] <= "10:10"
    assert "16:00" <= planned["16:00-16:10"] <= "16:10"
