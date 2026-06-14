from pathlib import Path


def test_windows_task_scripts_define_expected_schedule():
    register_script = Path("scripts/register_windows_tasks.ps1").read_text(encoding="utf-8")
    run_script = Path("scripts/run_fetch.ps1").read_text(encoding="utf-8")

    assert "NintendoGamePrice" in register_script
    assert "10:00" in register_script
    assert "16:00" in register_script
    assert "Register-ScheduledTask" in register_script
    assert "run_fetch.ps1" in register_script

    assert '"main.py", "--config", $Config, "fetch"' in run_script
    assert "--dry-run" in run_script
    assert "--no-report" in run_script


def test_xhs_today_script_wraps_publish_flow():
    script = Path("scripts/publish_xhs_today.py").read_text(encoding="utf-8")

    assert "build_publish_pack" in script
    assert "publish_to_xiaohongshu" in script
    assert "--publish" in script
    assert "--no-launch-edge" in script
    assert "latest_existing_session" in script
