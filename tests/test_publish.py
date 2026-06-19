import json
from pathlib import Path

from nsg_price.publish import build_caption, build_publish_pack, summarize_today_prices
from nsg_price.xiaohongshu import split_body_and_tags


def test_summarize_today_prices_counts_statuses():
    summary = summarize_today_prices(
        [
            {
                "prices": [
                    {"status": "ok"},
                    {"status": "unavailable"},
                    {"status": "missing"},
                ]
            },
            {"prices": [{"status": "missing"}]},
        ]
    )
    assert summary == {
        "game_count": 2,
        "games_with_price": 1,
        "ok_count": 1,
        "unavailable_count": 1,
        "missing_count": 2,
    }


def test_build_publish_pack_from_existing_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report_dir = Path("data/reports/2026-06-06")
    report_dir.mkdir(parents=True)
    (report_dir / "01_today_prices.png").write_bytes(b"first")
    (report_dir / "02_trend.png").write_bytes(b"second")
    (report_dir / "today_prices.json").write_text(
        json.dumps([{"game_name": "塞尔达", "prices": [{"status": "ok"}, {"status": "unavailable"}]}], ensure_ascii=False),
        encoding="utf-8",
    )

    output_dir, outputs = build_publish_pack({}, target_date="2026-06-06", regenerate_report=False)

    assert output_dir == Path("data/publish/2026-06-06")
    assert not (output_dir / "01.png").exists()
    assert "Switch 卡带回收价记录" in (output_dir / "caption.txt").read_text(encoding="utf-8")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["ok_count"] == 1
    assert manifest["images"][0]["file"] == "data\\reports\\2026-06-06\\01_today_prices.png"
    assert manifest["images"][1]["file"] == "data\\reports\\2026-06-06\\02_trend.png"
    assert len([path for path in outputs if path.suffix == ".png"]) == 0


def test_build_publish_pack_uses_session_directory_and_caption(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report_dir = Path("data/reports/2026-06-06/am")
    report_dir.mkdir(parents=True)
    (report_dir / "01_today_prices.png").write_bytes(b"first")
    (report_dir / "today_prices.json").write_text(
        json.dumps([{"game_name": "塞尔达", "prices": [{"status": "ok"}]}], ensure_ascii=False),
        encoding="utf-8",
    )

    output_dir, _ = build_publish_pack({}, target_date="2026-06-06", target_session="am", regenerate_report=False)

    assert output_dir == Path("data/publish/2026-06-06/am")
    caption = (output_dir / "caption.txt").read_text(encoding="utf-8")
    assert "2026-06-06 上午" in caption
    assert "如有想要记录的卡带请评论哦！" in caption
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["session"] == "am"


def test_caption_keeps_comment_prompt_before_tags():
    summary = {
        "game_count": 1,
        "games_with_price": 1,
        "ok_count": 1,
        "unavailable_count": 0,
        "missing_count": 0,
    }
    caption = build_caption("2026-06-16", summary, "pm")
    body = "\n".join(caption.splitlines()[1:]).strip()
    main_body, tags = split_body_and_tags(body)

    assert "\u5982\u6709\u60f3\u8981\u8bb0\u5f55\u7684\u5361\u5e26\u8bf7\u8bc4\u8bba\u54e6\uff01" in main_body
    assert caption.index("\u5982\u6709\u60f3\u8981\u8bb0\u5f55\u7684\u5361\u5e26\u8bf7\u8bc4\u8bba\u54e6\uff01") < caption.index("#")
    assert all("\u8bc4\u8bba" not in tag for tag in tags)


def test_caption_uses_fixed_requested_template():
    summary = {
        "game_count": 3,
        "games_with_price": 2,
        "ok_count": 5,
        "unavailable_count": 1,
        "missing_count": 0,
    }

    caption = build_caption("2026-06-16", summary)

    assert caption == "\n".join(
        [
            "Switch 卡带回收价记录｜2026-06-16",
            "",
            "前面为本次各回收商价格总表，后续页面展示回收价走势。",
            "价格仅作记录参考，实际回收价以各平台当时页面为准。",
            "如有想要记录的卡带请评论哦！",
            "",
            "#任天堂Switch #Switch卡带 #游戏回收 #二手游戏 #价格记录",
        ]
    )
