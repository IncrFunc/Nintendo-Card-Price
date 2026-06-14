from nsg_price.aggregation import build_daily_average_series


def test_daily_average_uses_latest_record_per_merchant_per_day():
    records = [
        {
            "merchant": "laolieren",
            "merchant_name": "老猎人",
            "game_slug": "zelda",
            "recycle_price": 100,
            "status": "ok",
            "fetched_at": "2026-06-06T10:00:00+08:00",
        },
        {
            "merchant": "laolieren",
            "merchant_name": "老猎人",
            "game_slug": "zelda",
            "recycle_price": 120,
            "status": "ok",
            "fetched_at": "2026-06-06T16:00:00+08:00",
        },
        {
            "merchant": "huoqiangshou",
            "merchant_name": "火枪手",
            "game_slug": "zelda",
            "recycle_price": 200,
            "status": "ok",
            "fetched_at": "2026-06-06T10:01:00+08:00",
        },
    ]
    daily = build_daily_average_series(records, "zelda")
    assert daily[0]["avg_price"] == 160
    assert {item["merchant"]: item["price"] for item in daily[0]["merchant_prices"]} == {"老猎人": 120, "火枪手": 200}
