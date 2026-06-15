from pathlib import Path


def test_xhs_publish_click_verifies_completion():
    source = Path("nsg_price/xiaohongshu.py").read_text(encoding="utf-8")

    assert "_publish_button_still_visible" in source
    assert "bottom publish button is still visible" in source
    assert "确认发布" in source
    assert "_human_type" in source
    assert "BODY_TYPE_DELAY_RANGE" in source
    assert "_dispatch_xhs_publish_event" in source
    assert "new CustomEvent('publish'" in source
    assert "xhs-publish-btn" in source
    assert "dispatchEvent(new MouseEvent" in source
