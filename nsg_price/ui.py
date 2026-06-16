from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import load_config, save_config
from .config_tools import add_game, remove_game, set_id, update_game
from .search_ids import apply_search_matches, build_search_matches


INDEX_HTML_PATH = Path(__file__).with_name("ui_assets") / "index.html"
UI_ASSET_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


def index_html() -> str:
    return INDEX_HTML_PATH.read_text(encoding="utf-8")


INDEX_HTML = index_html()


def ui_asset_path(name: str) -> Path:
    root = INDEX_HTML_PATH.parent.resolve()
    path = (root / name).resolve()
    if root not in path.parents or path.suffix not in UI_ASSET_TYPES:
        raise FileNotFoundError(name)
    return path


class GameManagerHandler(BaseHTTPRequestHandler):
    config_path = "config.json"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server API
        return

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length") or "0")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                body = index_html().encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path.startswith("/assets/"):
                asset = ui_asset_path(parsed.path[len("/assets/") :])
                body = asset.read_bytes()
                self.send_response(200)
                self.send_header("content-type", UI_ASSET_TYPES[asset.suffix])
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/config":
                config = load_config(self.config_path, resolve_env_vars=False)
                self.send_json(
                    {
                        "settings": config.get("settings", {}),
                        "merchants": config.get("merchants", {}),
                        "games": config.get("games", []),
                    }
                )
            elif parsed.path == "/api/search":
                query = parse_qs(parsed.query)
                game_slug = query.get("game", [""])[0]
                apply = query.get("apply", ["0"])[0] in ("1", "true", "yes")
                keyword = query.get("keyword", [""])[0].strip()
                config = load_config(self.config_path, resolve_env_vars=False)
                matches = build_search_matches(
                    config,
                    game_slug=game_slug,
                    search_keywords=[keyword] if keyword else None,
                    top=5,
                    page_size=10,
                )
                updated = 0
                if apply:
                    updated = apply_search_matches(config, matches, threshold=0.75, overwrite=False)
                    save_config(config, self.config_path)
                self.send_json({"matches": matches, "updated": updated})
            else:
                self.send_json({"error": "not found"}, status=404)
        except Exception as exc:  # noqa: BLE001 - UI should return actionable errors.
            self.send_json({"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/search/apply":
                payload = self.read_json()
                game_slug = str(payload.get("game_slug") or "").strip()
                merchant = str(payload.get("merchant") or "").strip()
                game_id = str(payload.get("game_id") or "").strip()
                uuid = str(payload.get("uuid") or "").strip()
                if not game_slug or not merchant or not game_id:
                    self.send_json({"error": "game_slug, merchant and game_id are required"}, status=400)
                    return
                config = load_config(self.config_path, resolve_env_vars=False)
                set_id(config, slug=game_slug, merchant=merchant, game_id=game_id, uuid=uuid or None)
                save_config(config, self.config_path)
                self.send_json({"game_slug": game_slug, "merchant": merchant, "game_id": game_id})
                return
            if parsed.path == "/api/games/reorder":
                payload = self.read_json()
                slug = str(payload.get("slug") or "").strip()
                direction = str(payload.get("direction") or "").strip()
                target_slug = str(payload.get("target_slug") or "").strip()
                placement = str(payload.get("placement") or "before").strip()
                config = load_config(self.config_path, resolve_env_vars=False)
                games = config.get("games", [])
                index = next((i for i, game in enumerate(games) if game.get("slug") == slug), -1)
                if index < 0:
                    self.send_json({"error": f"Game not found: {slug}"}, status=404)
                    return
                if target_slug:
                    target = next((i for i, game in enumerate(games) if game.get("slug") == target_slug), -1)
                    if target < 0:
                        self.send_json({"error": f"Target game not found: {target_slug}"}, status=404)
                        return
                    if target == index:
                        self.send_json({"slug": slug, "moved": False})
                        return
                    game = games.pop(index)
                    if index < target:
                        target -= 1
                    if placement == "after":
                        target += 1
                    elif placement != "before":
                        self.send_json({"error": "placement must be before or after"}, status=400)
                        return
                    target = max(0, min(target, len(games)))
                    games.insert(target, game)
                else:
                    if direction == "up":
                        target = index - 1
                    elif direction == "down":
                        target = index + 1
                    else:
                        self.send_json({"error": "direction must be up or down"}, status=400)
                        return
                    if target < 0 or target >= len(games):
                        self.send_json({"slug": slug, "moved": False})
                        return
                    games[index], games[target] = games[target], games[index]
                config["games"] = games
                save_config(config, self.config_path)
                self.send_json({"slug": slug, "moved": True})
                return
            if parsed.path.startswith("/api/merchants/"):
                merchant_key = parsed.path[len("/api/merchants/") :]
                payload = self.read_json()
                config = load_config(self.config_path, resolve_env_vars=False)
                merchant = config.get("merchants", {}).get(merchant_key)
                if not merchant:
                    self.send_json({"error": f"Merchant not found: {merchant_key}"}, status=404)
                    return
                merchant["enabled"] = bool(payload.get("enabled", True))
                save_config(config, self.config_path)
                self.send_json({"merchant": merchant_key, "enabled": merchant["enabled"]})
                return
            if parsed.path != "/api/games":
                self.send_json({"error": "not found"}, status=404)
                return
            payload = self.read_json()
            slug = str(payload.get("slug") or "").strip()
            name = str(payload.get("name") or "").strip()
            if not slug or not name:
                self.send_json({"error": "slug and name are required"}, status=400)
                return
            config = load_config(self.config_path, resolve_env_vars=False)
            original_slug = str(payload.get("original_slug") or "").strip()
            if original_slug:
                update_game(
                    config,
                    slug=original_slug,
                    new_slug=slug,
                    name=name,
                    platform=str(payload.get("platform") or "Nintendo Switch"),
                    search_keyword=str(payload.get("search_keyword") or ""),
                    enabled=bool(payload.get("enabled", True)),
                )
            else:
                add_game(config, slug=slug, name=name, platform=str(payload.get("platform") or "Nintendo Switch"))
                update_game(
                    config,
                    slug=slug,
                    search_keyword=str(payload.get("search_keyword") or ""),
                    enabled=bool(payload.get("enabled", True)),
                )
            for merchant, ids in (payload.get("merchant_ids") or {}).items():
                if not isinstance(ids, dict):
                    continue
                set_id(
                    config,
                    slug=slug,
                    merchant=str(merchant),
                    game_id=str(ids.get("game_id") or ""),
                    uuid=None if str(merchant) == "hangzhouxizi" else str(ids.get("uuid") or "") if "uuid" in ids else None,
                )
            save_config(config, self.config_path)
            self.send_json({"slug": slug})
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, status=500)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            prefix = "/api/games/"
            if not parsed.path.startswith(prefix):
                self.send_json({"error": "not found"}, status=404)
                return
            slug = parsed.path[len(prefix) :]
            config = load_config(self.config_path, resolve_env_vars=False)
            remove_game(config, slug=slug)
            save_config(config, self.config_path)
            self.send_json({"deleted": slug})
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, status=500)


def run_ui(*, config_path: str = "config.json", host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    handler = type("ConfiguredGameManagerHandler", (GameManagerHandler,), {"config_path": config_path})
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}"
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    print(f"game manager ui: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("ui stopped")
    finally:
        server.server_close()
