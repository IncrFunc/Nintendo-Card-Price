import random
from datetime import datetime
from pathlib import Path

from nsg_price.automation import pick_time_in_window, planned_publish_times_for_date, run_daily_automation, run_xhs_adb_publish, scheduled_time_is_due


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


def test_scheduled_time_is_due_after_planned_minute():
    assert scheduled_time_is_due(datetime(2026, 6, 15, 12, 8), "11:50") is True
    assert scheduled_time_is_due(datetime(2026, 6, 15, 11, 49), "11:50") is False


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


def test_daily_automation_catches_up_overdue_fetch(monkeypatch):
    calls = []
    monkeypatch.setattr("nsg_price.automation.run_fetch_and_pack", lambda config, **kwargs: calls.append(kwargs["target_date"]))

    run_daily_automation(
        {},
        fetch_times=["00:00"],
        publish_times=["23:59"],
        once=True,
        poll_seconds=0,
        log=lambda message: None,
    )

    assert calls == [datetime.now().date().isoformat()]


def test_adb_publish_uses_date_publish_directory(monkeypatch, tmp_path):
    calls = []

    class Result:
        status = "submitted"
        serial = "emulator-5554"
        image_count = 3
        remote_dir = "/sdcard/Pictures/NintendoGamePrice/2026-06-25"
        remote_deleted = True
        screenshot = Path("shot.png")

    def fake_publish(pack_dir, **kwargs):
        calls.append((pack_dir, kwargs))
        return Result()

    monkeypatch.setattr("nsg_price.automation.publish_pack_via_adb", fake_publish)

    event = run_xhs_adb_publish(
        {"settings": {"storage": {"publish_dir": str(tmp_path / "publish"), "runtime_dir": str(tmp_path / "runtime")}}},
        target_date="2026-06-25",
        adb_path="adb.exe",
        serial="emulator-5554",
        log=lambda message: None,
    )

    assert event.kind == "xhs-adb-publish"
    assert calls[0][0] == tmp_path / "publish" / "2026-06-25"
    assert calls[0][1]["publish"] is True
    assert calls[0][1]["adb_path"] == "adb.exe"
    assert calls[0][1]["serial"] == "emulator-5554"
    assert "remote_deleted=True" in event.message


def test_daily_automation_defaults_to_noon_adb():
    source = Path("nsg_price/automation.py").read_text(encoding="utf-8")
    assert '["11:50"]' in source
    assert '["12:00-12:10"]' in source
    assert "publish_driver" not in source
    assert "session_for_schedule_time" not in source
