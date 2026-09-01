from pathlib import Path


def test_linux_scripts_and_systemd_example_are_available():
    run_fetch = Path("scripts/run_fetch.sh").read_text(encoding="utf-8")
    run_auto = Path("scripts/run_auto_linux.sh").read_text(encoding="utf-8")
    service = Path("scripts/systemd/nintendo-game-price.service.example").read_text(encoding="utf-8")
    docs = Path("docs/linux.md").read_text(encoding="utf-8")

    assert "python3" in run_fetch
    assert "DRY_RUN" in run_fetch
    assert "main.py --config" in run_fetch
    assert "auto --ui" in run_auto
    assert "--publish-driver" not in run_auto
    assert "PUBLISH_DRIVER" not in run_auto
    assert "ADB_DEVICE" in run_auto
    assert "UI_HOST" in run_auto
    assert "Nintendo Game Price daily automation" in service
    assert "Restart=always" in service
    assert "xhs-edge" not in docs
    assert "systemd" in docs


def test_browser_publish_helper_was_removed():
    assert not Path("scripts/publish_xhs_today.py").exists()
