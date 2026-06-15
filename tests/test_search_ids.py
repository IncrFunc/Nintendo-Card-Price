from nsg_price.search_ids import (
    apply_search_matches,
    build_search_matches,
    candidates_for_game,
    normalize_search_records,
    search_keywords_for_game,
)


def test_normalize_search_records_for_captured_shapes():
    laolieren = normalize_search_records(
        "laolieren",
        {"rows": [{"id": "3174", "title": "NS 星之卡比探索发现", "platform": "switch"}]},
    )
    hailuo = normalize_search_records(
        "hailuo",
        {"data": [{"id": 1029, "store_name": "NS 星之卡比 探索发现", "price": 219}]},
    )
    xizi = normalize_search_records(
        "hangzhouxizi",
        {"data": {"list": [{"id": 1882, "name": "NS2游戏 星之卡比 卡比的飞天骑士 驭天飞行者"}]}},
        uuid="uuid-xizi",
    )
    mogushijian = normalize_search_records(
        "mogushijian",
        {"list": [{"cardsId": 2500, "name": "塞尔达传说：旷野之息", "price": 212, "generationType": 1}]},
    )

    assert laolieren[0]["item_id"] == "3174"
    assert hailuo[0]["name"] == "NS 星之卡比 探索发现"
    assert xizi[0]["uuid"] == "uuid-xizi"
    assert mogushijian[0]["item_id"] == "2500"
    assert mogushijian[0]["name"] == "塞尔达传说：旷野之息"


def test_search_keywords_include_rules_and_custom_keyword():
    game = {
        "slug": "zelda-tears-of-the-kingdom",
        "name": "塞尔达传说 王国之泪",
        "search_keyword": "王国之泪",
    }

    keywords = search_keywords_for_game(game)

    assert keywords[0] == "王国之泪"
    assert "塞尔达传说 王国之泪" in keywords


def test_build_and_apply_search_matches(monkeypatch):
    config = {
        "settings": {"request": {}},
        "merchants": {"laolieren": {"name": "老猎人"}},
        "games": [
            {
                "slug": "kirby-and-the-forgotten-land",
                "name": "星之卡比 探索发现",
                "platform": "Nintendo Switch",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": ""}},
            }
        ],
    }

    def fake_search_all_merchants(keyword, **kwargs):
        assert "探索发现" in keyword
        return {
            "laolieren": {
                "status": "ok",
                "records": [{"name": "NS 星之卡比探索发现", "item_id": "3174"}],
            }
        }

    monkeypatch.setattr("nsg_price.search_ids.search_all_merchants", fake_search_all_merchants)

    matches = build_search_matches(config, game_slug="kirby-and-the-forgotten-land", merchant="laolieren")
    updated = apply_search_matches(config, matches, threshold=0.5)

    assert matches[0]["status"] == "matched"
    assert updated == 1
    assert config["games"][0]["merchant_ids"]["laolieren"]["game_id"] == "3174"


def test_unruled_game_requires_name_core_for_auto_match():
    game = {"slug": "pikimin-4", "name": "皮克敏4", "platform": "Nintendo Switch"}
    rows = [
        {"game_name": "NS2 密特罗德究极4 穿越未知", "game_id": "3535"},
        {"game_name": "皮克敏4", "game_id": "2954"},
        {"game_name": "NS1 皮克敏4", "game_id": "bbb"},
    ]

    candidates = candidates_for_game(game, "huoqiangshou", rows, top=3)

    assert candidates[0]["matched_name"] == "皮克敏4"
    assert candidates[0]["rule_passed"] is True
    assert candidates[1]["matched_name"] == "NS1 皮克敏4"
    assert candidates[1]["rule_passed"] is True
    assert candidates[2]["matched_name"] == "NS2 密特罗德究极4 穿越未知"
    assert candidates[2]["rule_passed"] is False
