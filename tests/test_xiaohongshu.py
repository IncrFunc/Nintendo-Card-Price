from pathlib import Path


def test_xhs_publish_click_verifies_completion():
    source = Path("nsg_price/xiaohongshu.py").read_text(encoding="utf-8")

    assert "_publish_button_still_visible" in source
    assert "bottom publish button is still visible" in source
    assert "确认发布" in source
    assert "_human_type" in source
    assert "_human_wait" in source
    assert "TITLE_TYPE_DELAY_RANGE" in source
    assert "BODY_PASTE_DELAY_RANGE" in source
    assert "TITLE_TYPE_DELAY_RANGE = (1500, 2500)" in source
    assert "BODY_PASTE_DELAY_RANGE = (900, 1800)" in source
    assert "TAG_TYPE_DELAY_RANGE = (1500, 2500)" in source
    assert "CLICK_DELAY_RANGE" in source
    assert "UPLOAD_PICKER_DELAY_RANGE" in source
    assert "UPLOAD_SETTLE_PER_IMAGE_DELAY_RANGE" in source
    assert "OPEN_BEFORE_UPLOAD_MS = 20000" in source
    assert "AFTER_UPLOAD_BEFORE_COPY_MS = 10000" in source
    assert "EDIT_MINIMUM_DURATION_MS = 180000" in source
    assert "box[\"x\"] < 0 or box[\"y\"] < 0" in source
    assert "_wait_for_minimum_edit_duration" in source
    assert "await _wait_for_minimum_edit_duration(page, edit_started_at)" in source
    assert "TAG_INTERVAL_MS = 1000" in source
    assert "_insert_text" in source
    assert "page.expect_file_chooser" in source
    assert "_click_upload_entry" in source
    assert "file_chooser.set_files" in source
    assert "_human_click_locator" in source
    assert "_random_mouse_click" in source
    assert "await _human_type(page, title, TITLE_TYPE_DELAY_RANGE)" in source
    assert "await _paste_text(page, main_body)" in source
    assert "await _human_type(page, f\"#{tag}\", TAG_TYPE_DELAY_RANGE)" in source
    assert "before_publish_screenshot = screenshot_dir / \"xhs_before_publish.png\"" in source
    assert "before_publish_screenshot=before_publish_screenshot" in source
    assert "publish_screenshot_dir" in source
    assert "manifest.get(\"report_dir\")" in source
    assert "_dispatch_xhs_publish_event" in source
    assert "new CustomEvent('publish'" in source
    assert "xhs-publish-btn" in source
    assert "dispatchEvent(new MouseEvent" in source


def test_xhs_browser_launcher_supports_linux_candidates():
    source = Path("nsg_price/xiaohongshu.py").read_text(encoding="utf-8")

    assert "LINUX_BROWSER_CANDIDATES" in source
    assert "google-chrome" in source
    assert "chromium-browser" in source
    assert "default_xhs_profile_dir" in source
    assert "find_xhs_browser_executable" in source
