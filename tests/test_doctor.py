from nsg_price.doctor import build_doctor_report, expected_report_files, format_doctor_report


def test_doctor_report_summarizes_tokens_ids_and_reports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HAILUO_AUTHORIZATION", raising=False)
    config = {
        "settings": {"daily_fetch_times": ["09:55", "15:55"]},
        "merchants": {
            "laolieren": {"name": "老猎人", "enabled": True},
            "hailuo": {"name": "海螺", "enabled": True, "requires_env": ["HAILUO_AUTHORIZATION"]},
        },
        "games": [
            {
                "slug": "zelda",
                "name": "塞尔达",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": "154"}, "hailuo": {"game_id": ""}},
            }
        ],
    }
    report_dir = tmp_path / "data" / "reports" / "2026-06-06"
    report_dir.mkdir(parents=True)
    (report_dir / "01_today_prices.png").write_text("png", encoding="utf-8")
    (report_dir / "02_trend.png").write_text("png", encoding="utf-8")
    (report_dir / "today_prices.json").write_text(
        '[{"game_slug":"zelda","prices":[{"status":"ok"}]}]',
        encoding="utf-8",
    )
    (report_dir / "trend_series.json").write_text(
        '[{"game_slug":"zelda","daily_average":[]}]',
        encoding="utf-8",
    )
    publish_dir = tmp_path / "data" / "publish" / "2026-06-06"
    publish_dir.mkdir(parents=True)
    (publish_dir / "caption.txt").write_text("caption", encoding="utf-8")
    (publish_dir / "manifest.json").write_text(
        '{"images":[{"file":"data/reports/2026-06-06/01_today_prices.png"},{"file":"data/reports/2026-06-06/02_trend.png"}]}',
        encoding="utf-8",
    )

    report = build_doctor_report(config, target_date="2026-06-06")
    assert report["daily_fetch_times"] == ["09:55", "15:55"]
    assert report["required_env"] == {"HAILUO_AUTHORIZATION": False}
    assert report["id_coverage"]["filled"] == 1
    assert report["id_coverage"]["total_slots"] == 2
    assert report["report"]["png_count"] == 2
    assert report["report"]["expected_png_count"] == 2
    assert "01_today_prices.svg" in report["report"]["missing_expected"]
    assert report["task_readiness"]["checks"]["schedule_has_0955_and_1555"]["ok"] is True
    assert report["task_readiness"]["checks"]["today_table_covers_enabled_games"]["ok"] is True
    assert report["task_readiness"]["checks"]["trend_data_covers_enabled_games"]["ok"] is True
    assert report["task_readiness"]["checks"]["trend_pages_hold_six_games_each"]["ok"] is True
    assert report["task_readiness"]["checks"]["publish_pack_ready"]["ok"] is True

    text = format_doctor_report(report)
    assert "id_coverage: 1/2" in text
    assert "HAILUO_AUTHORIZATION=missing" in text
    assert "png=2/2" in text
    assert "task_readiness: 6/6 checks ok" in text
    assert "hailuo/zelda" in text


def test_expected_report_files_scales_with_six_games_per_trend_page():
    files = expected_report_files(26)
    assert len(files["png"]) == 6
    assert len(files["svg"]) == 6
    assert files["png"][0] == "01_today_prices.png"
    assert files["png"][-1] == "06_trend.png"


def test_expected_report_files_splits_today_pages_after_28_games():
    files = expected_report_files(30)
    assert files["png"][0] == "01_today_prices.png"
    assert files["png"][1] == "02_today_prices.png"
    assert files["png"][2] == "03_trend.png"
