from nsg_price import api_test


def test_api_test_uses_receive_price_fallback_when_other_shop_reduce_missing(monkeypatch):
    config = {
        "settings": {"request": {}},
        "games": [
            {
                "slug": "pokemon-legends-z-a",
                "name": "Pokemon Legends Z-A",
                "enabled": True,
                "merchant_ids": {"huoqiangshou": {"game_id": "3490"}},
            }
        ],
        "merchants": {
            "huoqiangshou": {
                "name": "Huoqiangshou",
                "enabled": True,
                "parser": "huoqiangshou",
                "endpoint": {
                    "method": "POST",
                    "url": "https://example.test/detail",
                    "data": {"productId": "{{game_id}}"},
                },
            }
        },
    }

    def fake_request_merchant_payload(_merchant, _endpoint, _request_settings):
        return {
            "detail": {
                "data": {
                    "id": 3490,
                    "productName": "Pokemon Legends Z-A",
                    "receivePrice": 280,
                    "retailPrice": 300,
                }
            },
            "apprize": {"data": {"listProductQuestion": []}},
        }

    monkeypatch.setattr(api_test, "request_merchant_payload", fake_request_merchant_payload)

    results = api_test.test_configured_apis(config)

    assert results[0]["status"] == "ok"
    assert results[0]["recycle_price"] == 280.0
    assert results[0]["parser_note"] == "huoqiangshou fallback recycle_price=detail.data.receivePrice"
