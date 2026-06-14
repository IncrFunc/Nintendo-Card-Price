import json

import pytest

from nsg_price.config_tools import add_game, init_task_games, remove_game, set_game_enabled, set_id, update_game, update_ids_from_file


def base_config():
    return {
        "games": [],
        "merchants": {
            "laolieren": {"name": "老猎人"},
            "hangzhouxizi": {"name": "杭州西子"},
        },
    }


def test_add_game_and_set_id():
    config = base_config()
    add_game(config, slug="test-game", name="测试游戏")
    set_id(config, slug="test-game", merchant="hangzhouxizi", game_id="42", uuid="uuid-42")
    ids = config["games"][0]["merchant_ids"]["hangzhouxizi"]
    assert ids["game_id"] == "42"
    assert ids["uuid"] == "uuid-42"


def test_add_game_rejects_duplicate():
    config = base_config()
    add_game(config, slug="test-game", name="测试游戏")
    with pytest.raises(ValueError):
        add_game(config, slug="test-game", name="测试游戏")


def test_update_game_edits_metadata_and_search_keyword():
    config = base_config()
    add_game(config, slug="test-game", name="测试游戏")

    update_game(
        config,
        slug="test-game",
        new_slug="renamed-game",
        name="新名字",
        platform="Nintendo Switch 2",
        search_keyword="新名字",
        enabled=False,
    )

    game = config["games"][0]
    assert game["slug"] == "renamed-game"
    assert game["name"] == "新名字"
    assert game["platform"] == "Nintendo Switch 2"
    assert game["search_keyword"] == "新名字"
    assert game["enabled"] is False
    assert set(game["merchant_ids"]) == {"laolieren", "hangzhouxizi"}


def test_update_ids_from_json(tmp_path):
    config = base_config()
    add_game(config, slug="test-game", name="测试游戏")
    path = tmp_path / "ids.json"
    path.write_text(json.dumps([{"slug": "test-game", "game_id": "100", "uuid": "u100"}]), encoding="utf-8")
    count = update_ids_from_file(config, merchant="hangzhouxizi", file_path=str(path))
    assert count == 1
    assert config["games"][0]["merchant_ids"]["hangzhouxizi"]["game_id"] == "100"
    assert config["games"][0]["merchant_ids"]["hangzhouxizi"]["uuid"] == "u100"


def test_init_task_games_and_enable_disable_remove():
    config = base_config()
    changed = init_task_games(config, replace=True)
    assert changed > 0
    assert len(config["games"]) == 26
    set_game_enabled(config, slug="zelda-breath-of-the-wild", enabled=False)
    assert config["games"][0]["enabled"] is False
    remove_game(config, slug="zelda-breath-of-the-wild")
    assert len(config["games"]) == 25
