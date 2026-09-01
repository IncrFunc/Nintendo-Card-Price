import json

from nsg_price.chart import generate_chart
from nsg_price.collector import collect, normalize_headers, request_merchant_payload
from nsg_price.storage import append_prices, load_prices


def test_fetch_missing_ids_does_not_crash(tmp_path):
    config = {
        "settings": {
            "request": {"save_raw_response": False},
            "storage": {"prices_path": str(tmp_path / "prices.db")},
        },
        "games": [
            {
                "slug": "zelda-tears-of-the-kingdom",
                "name": "Zelda Tears of the Kingdom",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": ""}},
            }
        ],
        "merchants": {
            "laolieren": {
                "name": "Laolieren",
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


def test_hangzhouxizi_request_payload_fetches_guige_from_detail(monkeypatch):
    calls = []

    def fake_request_json(endpoint, _request_settings):
        calls.append(endpoint)
        if "guige" in endpoint["url"]:
            return {"code": 1, "data": {"price": {"hs_price_2": 470}}}
        return {
            "code": 1,
            "data": {
                "goods": {"id": 50, "title": "NS Zelda"},
                "guige": [{"gg_value": [{"title": "二手中文盒装", "bianma": "detail-bianma"}]}],
            },
        }

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
            "_context": {"game_id": "50"},
        },
        {},
    )

    assert payload["detail"]["code"] == 1
    assert payload["detail"]["data"]["goods"]["id"] == 50
    assert calls[1]["json"] == {"id": "50", "guige": "detail-bianma"}


def test_hangzhouxizi_request_payload_ignores_config_bianma(monkeypatch):
    calls = []

    def fake_request_json(endpoint, _request_settings):
        calls.append(endpoint)
        if "guige" in endpoint["url"]:
            return {"code": 1, "data": {"price": {"hs_price_2": 470}}}
        return {
            "code": 1,
            "data": {
                "goods": {"id": 50, "title": "NS Zelda"},
                "guige": [
                    {
                        "title": "choose type",
                        "gg_value": [
                            {"title": "used boxed", "bianma": "detail-bianma-new"},
                        ],
                    }
                ],
            },
        }

    monkeypatch.setattr("nsg_price.collector.request_json", fake_request_json)

    request_merchant_payload(
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
            "_context": {"game_id": "50", "bianma": "old-config-bianma"},
        },
        {},
    )

    assert calls[1]["json"] == {"id": "50", "guige": "detail-bianma-new"}


def test_hangzhouxizi_request_payload_uses_configured_sku_id(monkeypatch):
    calls = []

    def fake_request_json(endpoint, _request_settings):
        calls.append(endpoint)
        if "guige" in endpoint["url"]:
            return {"code": 1, "data": {"price": {"hs_price_2": 470}}}
        return {
            "code": 1,
            "data": {
                "goods": {"id": 50, "title": "NS Zelda"},
                "guige": [
                    {
                        "title": "choose type",
                        "gg_value": [
                            {"id": 786, "title": "used boxed", "bianma": "boxed-bianma"},
                            {"id": 787, "title": "used dlc bundle", "bianma": "dlc-bianma"},
                        ],
                    }
                ],
            },
        }

    monkeypatch.setattr("nsg_price.collector.request_json", fake_request_json)

    request_merchant_payload(
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
            "_context": {"game_id": "50", "sku_id": "787"},
        },
        {},
    )

    assert calls[1]["json"] == {"id": "50", "guige": "dlc-bianma"}


def test_fetch_missing_ids_does_not_persist_skips(tmp_path):
    prices_path = tmp_path / "prices.db"
    config = {
        "settings": {
            "request": {"save_raw_response": False},
            "storage": {"prices_path": str(prices_path)},
        },
        "games": [
            {
                "slug": "zelda-tears-of-the-kingdom",
                "name": "Zelda Tears of the Kingdom",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": ""}},
            }
        ],
        "merchants": {
            "laolieren": {
                "name": "Laolieren",
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
    prices_path = tmp_path / "prices.db"
    config = {
        "settings": {
            "request": {"save_raw_response": False},
            "storage": {"prices_path": str(prices_path)},
        },
        "games": [
            {
                "slug": "zelda-tears-of-the-kingdom",
                "name": "Zelda Tears of the Kingdom",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": "3282"}},
            }
        ],
        "merchants": {
            "laolieren": {
                "name": "Laolieren",
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
    prices_path = tmp_path / "prices.db"
    chart_dir = tmp_path / "charts"
    append_prices(
        prices_path,
        [
                {
                    "merchant": "laolieren",
                    "merchant_name": "Laolieren",
                    "game_slug": "zelda-tears-of-the-kingdom",
                    "game_name": "Zelda Tears of the Kingdom",
                    "recycle_price": 210,
                    "status": "ok",
                    "fetched_at": "2026-06-01T09:30:00+08:00",
                },
                {
                    "merchant": "huoqiangshou",
                    "merchant_name": "Huoqiangshou",
                    "game_slug": "zelda-tears-of-the-kingdom",
                    "game_name": "Zelda Tears of the Kingdom",
                    "recycle_price": 220,
                    "status": "ok",
                    "fetched_at": "2026-06-01T09:31:00+08:00",
                },
        ],
    )
    output = generate_chart(
        {
            "settings": {
                "storage": {
                    "prices_path": str(prices_path),
                    "chart_dir": str(chart_dir),
                }
            }
        },
        "zelda-tears-of-the-kingdom",
    )
    assert output.exists()
    assert "Zelda Tears of the Kingdom" in output.read_text(encoding="utf-8")


def test_chart_escapes_html_from_price_records(tmp_path):
    prices_path = tmp_path / "prices.db"
    chart_dir = tmp_path / "charts"
    append_prices(
        prices_path,
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
    )

    output = generate_chart(
        {
            "settings": {
                "storage": {
                    "prices_path": str(prices_path),
                    "chart_dir": str(chart_dir),
                }
            }
        },
        "html-game",
    )
    html = output.read_text(encoding="utf-8")

    assert "Name &lt;script&gt;" in html
    assert "bad&lt;script&gt;" in html
