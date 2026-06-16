import random
from datetime import datetime

from nsg_price.automation import pick_time_in_window, planned_publish_times_for_date, run_daily_automation


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


def test_daily_automation_reloads_config_for_due_fetch(monkeypatch):
    seen_configs = []

    def fake_run_fetch_and_pack(config, **kwargs):
        seen_configs.append(config)

    monkeypatch.setattr("nsg_price.automation.run_fetch_and_pack", fake_run_fetch_and_pack)

    run_daily_automation(
        {"version": "startup"},
        config_loader=lambda: {"version": "fresh"},
        fetch_times=[datetime.now().strftime("%H:%M")],
        publish_times=["23:59"],
        once=True,
        poll_seconds=0,
        log=lambda message: None,
    )

    assert seen_configs == [{"version": "fresh"}]
