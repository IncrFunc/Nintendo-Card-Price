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

    buerjia = normalize_search_records(
        "buerjia",
        {"data": {"list": [{"gameId": 1024, "title": "NS Kirby Discovery", "price": 219}]}},
    )

    assert laolieren[0]["item_id"] == "3174"
    assert hailuo[0]["name"] == "NS 星之卡比 探索发现"
    assert xizi[0]["uuid"] == "uuid-xizi"
    assert mogushijian[0]["item_id"] == "2500"
    assert mogushijian[0]["name"] == "塞尔达传说：旷野之息"
    assert buerjia[0]["merchant"] == "buerjia"
    assert buerjia[0]["item_id"] == "1024"


def test_normalize_hangzhouxizi_goods_shape():
    rows = normalize_search_records(
        "hangzhouxizi",
        {"data": {"goods": [{"id": 71, "title": "NS星之卡比2探索发现", "price": 210}]}},
    )

    assert rows[0]["item_id"] == "71"
    assert rows[0]["name"] == "NS星之卡比2探索发现"


def test_normalize_buerjia_paginated_data_shape():
    rows = normalize_search_records(
        "buerjia",
        {"data": {"data": [{"id": 30, "name": "NS1 星之卡比新星同盟", "recycle_price": 120}]}},
    )

    assert rows[0]["item_id"] == "30"
    assert rows[0]["name"] == "NS1 星之卡比新星同盟"


def test_search_keywords_include_rules_and_custom_keyword():
    game = {
        "slug": "zelda-tears-of-the-kingdom",
        "name": "塞尔达传说 王国之泪",
        "search_keyword": "王国之泪",
    }

    keywords = search_keywords_for_game(game)

    assert keywords[0] == "王国之泪"
    assert "塞尔达传说 王国之泪" in keywords


def test_search_keywords_expand_explicit_synonyms():
    game = {
        "slug": "zelda-breath-of-the-wild",
        "name": "塞尔达传说 旷野之息",
        "search_keyword": "旷野之息",
    }

    keywords = search_keywords_for_game(game)

    assert "旷野之息" in keywords
    assert "荒野之息" in keywords


def test_build_search_matches_expands_override_search_keywords(monkeypatch):
    config = {
        "settings": {"request": {}},
        "merchants": {"hangzhouxizi": {"name": "杭州西子"}},
        "games": [
            {
                "slug": "zelda-breath-of-the-wild",
                "name": "塞尔达传说 旷野之息",
                "platform": "Nintendo Switch",
                "enabled": True,
                "merchant_ids": {"hangzhouxizi": {"game_id": ""}},
            }
        ],
    }
    seen = []

    def fake_search_all_merchants(keyword, **kwargs):
        seen.append(keyword)
        return {
            "hangzhouxizi": {
                "status": "ok",
                "records": [{"name": "NS 塞尔达传说 荒野之息", "item_id": "796"}],
            }
        }

    monkeypatch.setattr("nsg_price.search_ids.search_all_merchants", fake_search_all_merchants)

    matches = build_search_matches(
        config,
        game_slug="zelda-breath-of-the-wild",
        merchant="hangzhouxizi",
        search_keywords=["旷野之息"],
    )

    assert seen == [["旷野之息", "荒野之息"]]
    assert matches[0]["status"] == "matched"


def test_search_keywords_include_core_fragments_for_long_titles():
    dynasty = search_keywords_for_game({"slug": "dynasty-warriors", "name": "真三国无双 起源"})
    mario_party = search_keywords_for_game({"slug": "mario-party", "name": "超级马里奥派对 空前盛会"})

    assert "三国无双" in dynasty
    assert "起源" in dynasty
    assert "马里奥派对" in mario_party
    assert "空前盛会" in mario_party


def test_xenoblade1_keywords_include_common_merchant_aliases():
    keywords = search_keywords_for_game({"slug": "xenoblade1", "name": "异度之刃1"})

    assert "异度神剑" in keywords
    assert "xenoblade" in keywords
    assert "决定版" in keywords
    assert "终极版" in keywords


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


def test_build_search_matches_can_override_search_keywords(monkeypatch):
    config = {
        "settings": {"request": {}},
        "merchants": {"laolieren": {"name": "老猎人"}},
        "games": [
            {
                "slug": "xenoblade1",
                "name": "异度之刃1",
                "platform": "Nintendo Switch",
                "enabled": True,
                "merchant_ids": {"laolieren": {"game_id": ""}},
            }
        ],
    }
    seen = []

    def fake_search_all_merchants(keyword, **kwargs):
        seen.append(keyword)
        return {
            "laolieren": {
                "status": "ok",
                "records": [{"name": "异度之刃 决定版 终极版", "item_id": "1267"}],
            }
        }

    monkeypatch.setattr("nsg_price.search_ids.search_all_merchants", fake_search_all_merchants)

    matches = build_search_matches(config, game_slug="xenoblade1", merchant="laolieren", search_keywords=["异度神剑"])

    assert seen == [["异度神剑", "异度之刃", "xenoblade"]]
    assert matches[0]["keyword"] == "异度神剑, 异度之刃, xenoblade"
    assert matches[0]["status"] == "matched"


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


def test_xenoblade1_prefers_definitive_edition_over_numbered_sequels():
    game = {"slug": "xenoblade1", "name": "异度之刃1", "platform": "Nintendo Switch"}
    rows = [
        {"game_name": "异度之刃2", "game_id": "1273"},
        {"game_name": "异度之刃3", "game_id": "2370"},
        {"game_name": "异度之刃 决定版 终极版", "game_id": "1267"},
        {"game_name": "异度神剑：终极版", "game_id": "1664"},
        {"game_name": "NS2 异度之刃X", "game_id": "3592"},
    ]

    candidates = candidates_for_game(game, "huoqiangshou", rows, top=5)

    assert candidates[0]["game_id"] == "1267"
    assert candidates[0]["rule_passed"] is True
    assert candidates[1]["game_id"] == "1664"
    assert candidates[1]["rule_passed"] is True
    assert all(not item["rule_passed"] for item in candidates[2:])
