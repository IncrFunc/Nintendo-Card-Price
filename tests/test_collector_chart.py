import json

from nsg_price.chart import generate_chart
from nsg_price.collector import collect, normalize_headers, request_merchant_payload
from nsg_price.storage import load_prices


def test_fetch_missing_ids_does_not_crash(tmp_path):
    config = {
        "settings": {
            "request": {"save_raw_response": False},
            "storage": {"prices_json": str(tmp_path / "prices.json")},
        },
        "games": [
            {
                "slug": "zelda-tears-of-the-kingdom",
                "name": "塞尔达传说 王国之泪",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": ""}},
            }
        ],
        "merchants": {
            "laolieren": {
                "name": "老猎人",
                "enabled": True,
                "parser": "laolieren",
                "endpoint": {"method": "POST", "url": "https://example.test", "json": {"id": "{{game_id}}"}},
            }
        },
    }
    records = collect(config, dry_run=True)
    assert records[0]["status"] == "skipped"
    assert records[0]["error"] == "missing game_id"


def test_normalize_headers_converts_values_to_strings():
    headers = normalize_headers({"xweb_xhr": 1, "content-type": "application/json", "empty": ""})
    assert headers == {"xweb_xhr": "1", "content-type": "application/json"}


def test_hangzhouxizi_request_payload_fetches_guige_with_bianma(monkeypatch):
    calls = []

    def fake_request_json(endpoint, _request_settings):
        calls.append(endpoint)
        if "guige" in endpoint["url"]:
            return {"code": 1, "data": {"price": {"hs_price_2": 470}}}
        return {"code": 1, "data": {"goods": {"id": 50, "title": "NS塞尔达传说"}}}

    monkeypatch.setattr("nsg_price.collector.request_json", fake_request_json)

    payload = request_merchant_payload(
        {
            "parser": "hangzhouxizi",
            "guige_endpoint": {
                "method": "POST",
                "url": "https://xcx.hzxzdwsc.com/api/index/guige",
                "json": {"id": "{{game_id}}", "guige": "{{guige}}"},
            },
        },
        {
            "method": "POST",
            "url": "https://xcx.hzxzdwsc.com/api/index/detail",
            "json": {"id": "50"},
            "_context": {"game_id": "50", "bianma": "16941779810958560938"},
        },
        {},
    )

    assert payload["guige"]["data"]["price"]["hs_price_2"] == 470
    assert calls[1]["json"] == {"id": "50", "guige": "16941779810958560938"}


def test_fetch_missing_ids_does_not_persist_skips(tmp_path):
    prices_path = tmp_path / "prices.json"
    config = {
        "settings": {
            "request": {"save_raw_response": False},
            "storage": {"prices_json": str(prices_path)},
        },
        "games": [
            {
                "slug": "zelda-tears-of-the-kingdom",
                "name": "塞尔达传说 王国之泪",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": ""}},
            }
        ],
        "merchants": {
            "laolieren": {
                "name": "老猎人",
                "enabled": True,
                "parser": "laolieren",
                "endpoint": {"method": "POST", "url": "https://example.test", "json": {"id": "{{game_id}}"}},
            }
        },
    }
    records = collect(config)
    assert records[0]["status"] == "skipped"
    assert load_prices(prices_path) == []


def test_dry_run_with_configured_id_is_ready_without_request(tmp_path):
    prices_path = tmp_path / "prices.json"
    config = {
        "settings": {
            "request": {"save_raw_response": False},
            "storage": {"prices_json": str(prices_path)},
        },
        "games": [
            {
                "slug": "zelda-tears-of-the-kingdom",
                "name": "塞尔达传说 王国之泪",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": "3282"}},
            }
        ],
        "merchants": {
            "laolieren": {
                "name": "老猎人",
                "enabled": True,
                "parser": "laolieren",
                "endpoint": {"method": "POST", "url": "https://example.test", "json": {"id": "{{game_id}}" }},
            }
        },
    }
    records = collect(config, dry_run=True)
    assert records[0]["status"] == "ready"
    assert records[0]["error"] == "dry-run ready; remote API not called"
    assert not prices_path.exists()


def test_chart_generates_html(tmp_path):
    prices_path = tmp_path / "prices.json"
    chart_dir = tmp_path / "charts"
    prices_path.write_text(
        json.dumps(
            [
                {
                    "merchant": "laolieren",
                    "merchant_name": "老猎人",
                    "game_slug": "zelda-tears-of-the-kingdom",
                    "game_name": "塞尔达传说 王国之泪",
                    "recycle_price": 210,
                    "status": "ok",
                    "fetched_at": "2026-06-01T09:30:00+08:00",
                },
                {
                    "merchant": "huoqiangshou",
                    "merchant_name": "火枪手",
                    "game_slug": "zelda-tears-of-the-kingdom",
                    "game_name": "塞尔达传说 王国之泪",
                    "recycle_price": 220,
                    "status": "ok",
                    "fetched_at": "2026-06-01T09:31:00+08:00",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = generate_chart(
        {
            "settings": {
                "storage": {
                    "prices_json": str(prices_path),
                    "chart_dir": str(chart_dir),
                }
            }
        },
        "zelda-tears-of-the-kingdom",
    )
    assert output.exists()
    assert "塞尔达传说 王国之泪 回收价走势" in output.read_text(encoding="utf-8")


def test_chart_escapes_html_from_price_records(tmp_path):
    prices_path = tmp_path / "prices.json"
    chart_dir = tmp_path / "charts"
    prices_path.write_text(
        json.dumps(
            [
                {
                    "merchant": "bad<script>",
                    "merchant_name": "bad<script>",
                    "game_slug": "html-game",
                    "game_name": "Name <script>",
                    "recycle_price": 210,
                    "status": "ok",
                    "fetched_at": "2026-06-01T09:30:00+08:00",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = generate_chart(
        {
            "settings": {
                "storage": {
                    "prices_json": str(prices_path),
                    "chart_dir": str(chart_dir),
                }
            }
        },
        "html-game",
    )
    html = output.read_text(encoding="utf-8")

    assert "Name &lt;script&gt; 回收价走势" in html
    assert "bad&lt;script&gt;" in html
