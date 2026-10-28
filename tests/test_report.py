import json
from datetime import date, timedelta

from nsg_price.report import PIL_AVAILABLE, build_today_price_table, generate_report, today_column_centers, today_highlight_half_width, trend_average_series
from nsg_price.trend_chart import monthly_metrics, previous_month
from nsg_price.storage import append_prices


def test_generate_report_svg_pages(tmp_path, monkeypatch):
    prices_path = tmp_path / "prices.db"
    append_prices(
        prices_path,
        [
                {
                    "merchant": "laolieren",
                    "merchant_name": "老猎人",
                    "game_slug": "zelda-breath-of-the-wild",
                    "game_name": "塞尔达传说 旷野之息",
                    "recycle_price": 203,
                    "status": "ok",
                    "fetched_at": "2026-06-05T10:00:00+08:00",
                }
        ],
    )
    monkeypatch.chdir(tmp_path)
    config = {
        "settings": {"storage": {"prices_path": str(prices_path)}},
        "merchants": {"laolieren": {"name": "老猎人"}, "huoqiangshou": {"name": "火玱手"}},
        "games": [
            {"slug": "zelda-breath-of-the-wild", "name": "塞尔达传说 旷野之息", "enabled": True},
            {"slug": "missing-game", "name": "缺失游戏", "enabled": True},
        ],
    }
    outputs = generate_report(config, target_date="2026-06-05")
    svg_outputs = [path for path in outputs if path.suffix == ".svg"]
    png_outputs = [path for path in outputs if path.suffix == ".png"]
    json_outputs = [path for path in outputs if path.suffix == ".json"]
    assert len(svg_outputs) == 2
    assert {path.name for path in json_outputs} == {"today_prices.json", "trend_series.json"}
    if PIL_AVAILABLE:
        assert len(png_outputs) == 2
        assert all(path.exists() for path in png_outputs)
    today_svg = tmp_path / "data" / "reports" / "2026-06-05" / "01_today_prices.svg"
    text = today_svg.read_text(encoding="utf-8")
    assert "Switch 卡带今日回收价" in text
    assert "¥203" in text
    assert "-" in text
    today = json.loads((tmp_path / "data" / "reports" / "2026-06-05" / "today_prices.json").read_text(encoding="utf-8"))
    assert today[0]["prices"][0]["display_price"] == "¥203"
    assert len(today[0]["prices"]) == 1


def test_today_table_marks_highest_recycle_price():
    config = {
        "merchants": {
            "laolieren": {"name": "老猎人"},
            "huoqiangshou": {"name": "火玱手"},
            "hailuo": {"name": "海螺"},
            "baibiandui": {"name": "百变兑"},
            "hangzhouxizi": {"name": "杭州西子"},
        },
        "games": [{"slug": "zelda", "name": "塞尔达", "enabled": True}],
    }
    records = [
        {"merchant": "laolieren", "game_slug": "zelda", "status": "ok", "recycle_price": 200, "fetched_at": "2026-06-06T10:00:00+08:00"},
        {"merchant": "huoqiangshou", "game_slug": "zelda", "status": "ok", "recycle_price": 210, "fetched_at": "2026-06-06T10:00:00+08:00"},
        {"merchant": "hailuo", "game_slug": "zelda", "status": "unavailable", "recycle_price": None, "fetched_at": "2026-06-06T10:00:00+08:00"},
    ]

    row = build_today_price_table(config, records, "2026-06-06")[0]

    highest = [price["merchant"] for price in row["prices"] if price["is_highest"]]
    assert highest == ["huoqiangshou"]


def test_today_columns_spread_visible_merchants_evenly():
    _, four_columns = today_column_centers(4)
    _, five_columns = today_column_centers(5)
    _, six_columns = today_column_centers(6)
    _, seven_columns = today_column_centers(7)

    assert four_columns == [526, 658, 790, 922]
    assert five_columns == [513, 618, 724, 830, 935]
    assert six_columns == [504, 592, 680, 768, 856, 944]
    assert min(right - left for left, right in zip(seven_columns, seven_columns[1:])) >= 88
    assert today_highlight_half_width(6) == 40


def test_today_table_uses_latest_record_for_the_day():
    config = {
        "merchants": {"laolieren": {"name": "老猎人"}},
        "games": [{"slug": "zelda", "name": "塞尔达", "enabled": True}],
    }
    records = [
        {"merchant": "laolieren", "game_slug": "zelda", "status": "ok", "recycle_price": 200, "fetched_at": "2026-06-06T09:55:00+08:00", "session": "am"},
        {"merchant": "laolieren", "game_slug": "zelda", "status": "ok", "recycle_price": 230, "fetched_at": "2026-06-06T15:55:00+08:00", "session": "pm"},
    ]

    row = build_today_price_table(config, records, "2026-06-06")[0]

    assert row["prices"][0]["recycle_price"] == 230


def test_today_table_hides_merchant_when_current_run_all_failed():
    config = {
        "merchants": {
            "laolieren": {"name": "老猎人"},
            "huoqiangshou": {"name": "火玱手"},
        },
        "games": [{"slug": "zelda", "name": "塞尔达", "enabled": True}],
    }
    records = [
        {"merchant": "laolieren", "game_slug": "zelda", "status": "ok", "recycle_price": 200, "fetched_at": "2026-06-06T09:55:00+08:00", "session": "am"},
        {"merchant": "huoqiangshou", "game_slug": "zelda", "status": "error", "recycle_price": None, "fetched_at": "2026-06-06T09:55:00+08:00", "session": "am"},
    ]

    row = build_today_price_table(config, records, "2026-06-06")[0]

    assert [price["merchant"] for price in row["prices"]] == ["laolieren"]


def test_today_report_does_not_drop_games_after_26(tmp_path, monkeypatch):
    prices_path = tmp_path / "prices.db"
    monkeypatch.chdir(tmp_path)
    games = [
        {"slug": f"game-{index:02d}", "name": f"测试卡带{index:02d}", "enabled": True}
        for index in range(1, 31)
    ]
    config = {
        "settings": {"storage": {"prices_path": str(prices_path)}},
        "merchants": {"laolieren": {"name": "老猎人"}},
        "games": games,
    }

    outputs = generate_report(config, target_date="2026-06-05")

    today_svg = tmp_path / "data" / "reports" / "2026-06-05" / "01_today_prices.svg"
    text = today_svg.read_text(encoding="utf-8")
    assert "测试卡带01" in text
    assert "测试卡带28" in text
    second_today_svg = tmp_path / "data" / "reports" / "2026-06-05" / "02_today_prices.svg"
    second_text = second_today_svg.read_text(encoding="utf-8")
    assert "测试卡带29" in second_text
    assert "测试卡带30" in second_text

    today = json.loads((tmp_path / "data" / "reports" / "2026-06-05" / "today_prices.json").read_text(encoding="utf-8"))
    assert len(today) == 30
    today_svgs = [path for path in outputs if path.suffix == ".svg" and "today" in path.name]
    trend_svgs = [path for path in outputs if path.suffix == ".svg" and "trend" in path.name]
    assert len(today_svgs) == 2
    assert len(trend_svgs) == 4
    first_trend = trend_svgs[0].read_text(encoding="utf-8")
    assert "测试卡带08" in first_trend
    assert "测试卡带09" not in first_trend
    assert "测试卡带30" in trend_svgs[-1].read_text(encoding="utf-8")


def test_trend_chart_draws_entire_year_and_monthly_metrics(tmp_path, monkeypatch):
    prices_path = tmp_path / "prices.db"
    records = []
    start = date(2025, 5, 12)
    for index in range(400):
        day = start + timedelta(days=index)
        for session, hour, offset in (("am", 9, 0), ("pm", 15, 8)):
            records.append(
                {
                    "merchant": "laolieren",
                    "merchant_name": "老猎人",
                    "game_slug": "zelda",
                    "game_name": "塞尔达",
                    "recycle_price": 180 + ((index * 7 + offset) % 31),
                    "status": "ok",
                    "session": session,
                    "fetched_at": f"{day.isoformat()}T{hour:02d}:55:00+08:00",
                }
            )
    append_prices(prices_path, records)
    monkeypatch.chdir(tmp_path)
    config = {
        "settings": {"storage": {"prices_path": str(prices_path)}},
        "merchants": {"laolieren": {"name": "老猎人"}},
        "games": [{"slug": "zelda", "name": "塞尔达", "enabled": True}],
    }

    generate_report(config, target_date="2026-06-15")

    series = trend_average_series(records, "zelda", "2026-06-15")
    assert len(series) == 365
    assert series[0][0] == "2025-06-16"
    assert series[-1][0] == "2026-06-15"
    trend_svg = (tmp_path / "data" / "reports" / "2026-06-15" / "02_trend.svg").read_text(encoding="utf-8")
    import xml.etree.ElementTree as ET

    root = ET.fromstring(trend_svg)
    lines = root.findall("{http://www.w3.org/2000/svg}polyline")
    curve = next(line for line in lines if line.attrib.get("stroke") == "#426abd")
    assert len(curve.attrib["points"].split()) == 365
    assert root.attrib["height"] == "1390"
    assert "近一月最高均价" in trend_svg
    assert "近一月 " in trend_svg
    assert "上午" not in trend_svg
    assert "下午" not in trend_svg
    assert "Δ" not in trend_svg
    assert "次→" not in trend_svg
    assert "06/16" in trend_svg
    assert "06/15" in trend_svg


def test_monthly_metrics_use_calendar_month_and_latest_prior_record():
    series = [
        ("2026-08-01", "08-01", 500.0),
        ("2026-09-27", "09-27", 200.0),
        ("2026-10-01", "10-01", 220.0),
        ("2026-10-28", "10-28", 180.0),
    ]
    highest, change = monthly_metrics(series, date(2026, 10, 28))
    assert highest == 220
    assert round(change, 6) == -10
    assert previous_month(date(2026, 3, 31)) == date(2026, 2, 28)
    assert previous_month(date(2024, 3, 31)) == date(2024, 2, 29)
    assert previous_month(date(2026, 1, 31)) == date(2025, 12, 31)


def test_monthly_metrics_handle_short_history_stale_and_zero():
    assert monthly_metrics([], date(2026, 10, 28)) == (None, None)
    assert monthly_metrics([("2026-08-01", "08-01", 200)], date(2026, 10, 28)) == (None, None)
    highest, change = monthly_metrics([("2026-10-01", "10-01", 100), ("2026-10-28", "10-28", 110)], date(2026, 10, 28))
    assert highest == 110
    assert round(change, 6) == 10
    assert monthly_metrics([("2026-10-28", "10-28", 0)], date(2026, 10, 28)) == (0, None)


def test_regeneration_removes_obsolete_chart_pages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "data/reports/2026-10-28"
    output.mkdir(parents=True)
    obsolete = output / "10_trend.png"
    obsolete.write_bytes(b"old chart")
    keep = output / "personal.png"
    keep.write_bytes(b"user file")
    generate_report({"games": [], "merchants": {}, "settings": {"storage": {"prices_path": str(tmp_path / "prices.db")}}}, "2026-10-28")
    assert not obsolete.exists()
    assert keep.exists()
