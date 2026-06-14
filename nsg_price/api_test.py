from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .collector import has_empty_token, missing_required_env, request_merchant_payload
from .config import enabled_games
from .constants import DEFAULT_XIZI_UUID
from .parsers import PARSERS
from .utils import compact_json, render_template

LOGGER = logging.getLogger(__name__)
__test__ = False


def test_configured_apis(config: dict[str, Any], *, game_slug: str | None = None) -> list[dict[str, Any]]:
    request_settings = config.get("settings", {}).get("request", {})
    default_xizi_uuid = str(config.get("settings", {}).get("default_xizi_uuid") or DEFAULT_XIZI_UUID)
    merchants = config.get("merchants", {})
    checked_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    results: list[dict[str, Any]] = []

    for game in enabled_games(config, game_slug):
        for merchant_key, merchant in merchants.items():
            if not merchant.get("enabled", True):
                continue
            merchant_name = merchant.get("name", merchant_key)
            ids = game.get("merchant_ids", {}).get(merchant_key, {})
            game_id = ids.get("game_id") or ids.get("productId") or ids.get("id")
            base = {
                "checked_at": checked_at,
                "merchant": merchant_key,
                "merchant_name": merchant_name,
                "game_slug": game.get("slug"),
                "game_name": game.get("name"),
                "url": merchant.get("endpoint", {}).get("url"),
            }
            if not game_id:
                results.append({**base, "status": "skipped", "reason": "missing game_id"})
                continue
            if missing_required_env(merchant) or has_empty_token(merchant):
                results.append(
                    {
                        **base,
                        "status": "skipped",
                        "reason": "missing token/env: " + ",".join(missing_required_env(merchant)),
                    }
                )
                continue

            context = {**ids, "game_id": game_id}
            if merchant_key == "hangzhouxizi" and not context.get("uuid"):
                context["uuid"] = default_xizi_uuid
            endpoint = render_template(merchant.get("endpoint", {}), context)
            endpoint["_context"] = context
            parser = PARSERS.get(merchant.get("parser", merchant_key))
            if parser is None:
                results.append({**base, "status": "failed", "reason": "unknown parser"})
                continue
            try:
                raw = request_merchant_payload(merchant, endpoint, request_settings)
                parsed = parser(raw)
                results.append(
                    {
                        **base,
                        "status": parsed.status,
                        "http": "ok",
                        "parsed_game_name": parsed.game_name,
                        "item_id": parsed.item_id or str(game_id),
                        "sku_id": parsed.sku_id,
                        "sell_price": parsed.sell_price,
                        "recycle_price": parsed.recycle_price,
                        "parser_note": parsed.parser_note,
                        "reason": parsed.parser_note if parsed.status != "ok" else None,
                        "response_preview": compact_json(raw, max_length=1000),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - this is a diagnostic command.
                LOGGER.exception("API test failed for %s/%s", merchant_key, game.get("slug"))
                results.append({**base, "status": "failed", "reason": str(exc)})
    return results
