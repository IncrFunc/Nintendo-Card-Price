from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .config import find_game, save_config
from .utils import load_json


def empty_merchant_ids(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {key: {"game_id": ""} for key in config.get("merchants", {})}


def ensure_game_id_slots(config: dict[str, Any], game: dict[str, Any]) -> None:
    merchant_ids = game.setdefault("merchant_ids", {})
    for merchant in config.get("merchants", {}):
        ids = merchant_ids.setdefault(merchant, {"game_id": ""})
        ids.setdefault("game_id", "")


def add_game(config: dict[str, Any], *, slug: str, name: str, platform: str = "Nintendo Switch") -> None:
    if find_game(config, slug):
        raise ValueError(f"Game already exists: {slug}")
    config.setdefault("games", []).append(
        {
            "slug": slug,
            "name": name,
            "platform": platform,
            "enabled": True,
            "merchant_ids": empty_merchant_ids(config),
        }
    )


def update_game(
    config: dict[str, Any],
    *,
    slug: str,
    name: str | None = None,
    platform: str | None = None,
    search_keyword: str | None = None,
    enabled: bool | None = None,
    new_slug: str | None = None,
) -> None:
    game = find_game(config, slug)
    if not game:
        raise ValueError(f"Game not found: {slug}")
    if new_slug and new_slug != slug:
        if find_game(config, new_slug):
            raise ValueError(f"Game already exists: {new_slug}")
        game["slug"] = new_slug
    if name is not None:
        game["name"] = name
    if platform is not None:
        game["platform"] = platform
    if search_keyword is not None:
        if search_keyword:
            game["search_keyword"] = search_keyword
        else:
            game.pop("search_keyword", None)
    if enabled is not None:
        game["enabled"] = enabled
    ensure_game_id_slots(config, game)


def set_id(
    config: dict[str, Any],
    *,
    slug: str,
    merchant: str,
    game_id: str | None = None,
    uuid: str | None = None,
) -> None:
    game = find_game(config, slug)
    if not game:
        raise ValueError(f"Game not found: {slug}")
    if merchant not in config.get("merchants", {}):
        raise ValueError(f"Merchant not found: {merchant}")
    ids = game.setdefault("merchant_ids", {}).setdefault(merchant, {})
    if game_id is not None:
        ids["game_id"] = game_id
    if uuid is not None:
        ids["uuid"] = uuid


def set_game_enabled(config: dict[str, Any], *, slug: str, enabled: bool) -> None:
    game = find_game(config, slug)
    if not game:
        raise ValueError(f"Game not found: {slug}")
    game["enabled"] = enabled


def remove_game(config: dict[str, Any], *, slug: str) -> None:
    games = config.get("games", [])
    new_games = [game for game in games if game.get("slug") != slug]
    if len(new_games) == len(games):
        raise ValueError(f"Game not found: {slug}")
    config["games"] = new_games


def init_example_games(
    config: dict[str, Any],
    *,
    source_path: str | Path = "data/games.example.json",
    replace: bool = False,
) -> int:
    payload = load_json(source_path)
    templates = payload.get("games", []) if isinstance(payload, dict) else payload
    if not isinstance(templates, list):
        raise ValueError(f"example games file must contain a list: {source_path}")
    existing_by_slug = {game.get("slug"): game for game in config.get("games", [])}
    new_games = []
    changed = 0

    for template in templates:
        old = existing_by_slug.get(template["slug"], {})
        merchant_ids = old.get("merchant_ids") or empty_merchant_ids(config)
        item = {
            "slug": template["slug"],
            "name": template["name"],
            "platform": template["platform"],
            "enabled": old.get("enabled", True),
            "merchant_ids": merchant_ids,
        }
        ensure_game_id_slots(config, item)
        new_games.append(item)
        if old != item:
            changed += 1

    if replace:
        config["games"] = new_games
    else:
        untouched = [game for game in config.get("games", []) if game.get("slug") not in {item["slug"] for item in new_games}]
        config["games"] = new_games + untouched
    return changed


def save(config: dict[str, Any], path: str = "config.json") -> None:
    save_config(config, path)


def update_ids_from_file(config: dict[str, Any], *, merchant: str, file_path: str) -> int:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(file_path)
    rows: list[dict[str, Any]]
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("items", [])
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as fp:
            rows = list(csv.DictReader(fp))

    updated = 0
    for row in rows:
        slug = row.get("slug") or row.get("game_slug")
        game_id = row.get("game_id") or row.get("id") or row.get("productId")
        uuid = row.get("uuid") or None
        if not slug or not game_id:
            continue
        set_id(config, slug=slug, merchant=merchant, game_id=str(game_id), uuid=str(uuid) if uuid else None)
        updated += 1
    return updated
