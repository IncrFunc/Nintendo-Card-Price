import json

from nsg_price.config import load_config, save_config


def test_config_loads_and_saves_external_games(tmp_path):
    config_path = tmp_path / "config.json"
    games_path = tmp_path / "data" / "games.json"
    games_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "settings": {"games_file": "data/games.json"},
                "merchants": {"laolieren": {"name": "老猎人"}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    games_path.write_text(
        json.dumps([{"slug": "zelda", "name": "塞尔达", "enabled": True}], ensure_ascii=False),
        encoding="utf-8",
    )

    config = load_config(config_path, resolve_env_vars=False)
    assert config["games"][0]["slug"] == "zelda"

    config["games"][0]["name"] = "塞尔达传说"
    save_config(config, config_path)

    saved_config = json.loads(config_path.read_text(encoding="utf-8"))
    saved_games = json.loads(games_path.read_text(encoding="utf-8"))
    assert "games" not in saved_config
    assert saved_games[0]["name"] == "塞尔达传说"
