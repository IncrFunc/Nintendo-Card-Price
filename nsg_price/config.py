from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .utils import load_json, resolve_env, write_json


def ensure_config(path: str | Path) -> Path:
    path = Path(path)
    if not path.exists():
        example = Path("config.example.json")
        if not example.exists():
            raise FileNotFoundError("config.json not found and config.example.json is missing")
        shutil.copyfile(example, path)
    return path


def external_games_path(config: dict[str, Any], config_path: str | Path = "config.json") -> Path | None:
    games_file = config.get("settings", {}).get("games_file") or config.get("games_file")
    if not games_file:
        return None
    path = Path(str(games_file))
    if not path.is_absolute():
        path = Path(config_path).parent / path
    return path


def load_external_games(config: dict[str, Any], config_path: str | Path = "config.json") -> None:
    games_path = external_games_path(config, config_path)
    if not games_path or not games_path.exists():
        return
    payload = load_json(games_path)
    if isinstance(payload, dict):
        games = payload.get("games", [])
    else:
        games = payload
    if not isinstance(games, list):
        raise ValueError(f"games file must contain a list: {games_path}")
    config["games"] = games


def load_config(path: str | Path = "config.json", *, resolve_env_vars: bool = True) -> dict[str, Any]:
    load_dotenv()
    path = ensure_config(path)
    config = load_json(path)
    load_external_games(config, path)
    return resolve_env(config) if resolve_env_vars else config


def save_config(config: dict[str, Any], path: str | Path = "config.json") -> None:
    config_to_write = deepcopy(config)
    games_path = external_games_path(config_to_write, path)
    if games_path:
        write_json(games_path, config_to_write.get("games", []))
        config_to_write.pop("games", None)
    write_json(path, config_to_write)


def find_game(config: dict[str, Any], slug: str) -> dict[str, Any] | None:
    return next((game for game in config.get("games", []) if game.get("slug") == slug), None)


def enabled_games(config: dict[str, Any], slug: str | None = None) -> list[dict[str, Any]]:
    games = config.get("games", [])
    if slug:
        game = find_game(config, slug)
        return [game] if game and game.get("enabled", True) else []
    return [game for game in games if game.get("enabled", True)]
