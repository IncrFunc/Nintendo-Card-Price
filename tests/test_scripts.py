from pathlib import Path


def test_windows_task_scripts_define_expected_schedule():
    register_script = Path("scripts/register_windows_tasks.ps1").read_text(encoding="utf-8")
    run_script = Path("scripts/run_fetch.ps1").read_text(encoding="utf-8")

    assert "NintendoGamePrice" in register_script
    assert "09:50" in register_script
    assert "15:50" in register_script
    assert "Register-ScheduledTask" in register_script
    assert "run_fetch.ps1" in register_script

    assert '"main.py", "--config", $Config, "fetch"' in run_script
    assert "--dry-run" in run_script
    assert "--no-report" in run_script


def test_linux_scripts_and_systemd_example_are_available():
    run_fetch = Path("scripts/run_fetch.sh").read_text(encoding="utf-8")
    run_auto = Path("scripts/run_auto_linux.sh").read_text(encoding="utf-8")
    service = Path("scripts/systemd/nintendo-game-price.service.example").read_text(encoding="utf-8")
    docs = Path("docs/linux.md").read_text(encoding="utf-8")

    assert "python3" in run_fetch
    assert "DRY_RUN" in run_fetch
    assert "main.py --config" in run_fetch
    assert "auto --ui" in run_auto
    assert "--publish-driver" in run_auto
    assert "PUBLISH_DRIVER" in run_auto
    assert "ADB_DEVICE" in run_auto
    assert "UI_HOST" in run_auto
    assert "Nintendo Game Price daily automation" in service
    assert "Restart=always" in service
    assert "python main.py xhs-edge" in docs
    assert "systemd" in docs


def test_xhs_today_script_wraps_publish_flow():
    script = Path("scripts/publish_xhs_today.py").read_text(encoding="utf-8")

    assert "build_publish_pack" in script
    assert "publish_to_xiaohongshu" in script
    assert "before publish screenshot" in script
    assert "--publish" in script
    assert "--no-launch-edge" in script
    assert "latest_existing_session" in script
