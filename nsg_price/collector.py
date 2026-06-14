from __future__ import annotations

import logging
import os
import time
import warnings
from datetime import datetime, timezone
from typing import Any

import requests
import urllib3

from .config import enabled_games
from .constants import DEFAULT_XIZI_UUID
from .parsers import PARSERS
from .storage import append_prices
from .aggregation import session_for_time
from .utils import compact_json, render_template

LOGGER = logging.getLogger(__name__)


def missing_required_env(merchant: dict[str, Any]) -> list[str]:
    return [env_name for env_name in merchant.get("requires_env", []) if not os.getenv(env_name)]


def has_empty_token(merchant: dict[str, Any]) -> bool:
    endpoint = merchant.get("endpoint", {})
    headers = endpoint.get("headers", {})
    for value in headers.values():
        if isinstance(value, str) and value.strip().lower() == "bearer":
            return True
        if isinstance(value, str) and value.strip().lower() == "bearer ":
            return True
    return False


def make_error_record(
    *,
    merchant_key: str,
    merchant_name: str,
    game: dict[str, Any],
    error: str,
    fetched_at: str,
    session: str,
    status: str = "error",
) -> dict[str, Any]:
    return {
        "merchant": merchant_key,
        "merchant_name": merchant_name,
        "game_slug": game.get("slug"),
        "game_name": game.get("name"),
        "item_id": None,
        "sku_id": None,
        "sell_price": None,
        "recycle_price": None,
        "currency": "CNY",
        "status": status,
        "fetched_at": fetched_at,
        "session": session,
        "error": error,
    }


def persistable_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("status") not in {"ready", "skipped"}]


def request_json(endpoint: dict[str, Any], request_settings: dict[str, Any]) -> dict[str, Any]:
    method = endpoint.get("method", "GET").upper()
    timeout = int(request_settings.get("timeout_seconds", 10))
    retries = int(request_settings.get("retries", 2))
    backoff = float(request_settings.get("retry_backoff_seconds", 1))
    verify_ssl = bool(request_settings.get("verify_ssl", True))

    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

    last_error: Exception | None = None
    headers = normalize_headers(endpoint.get("headers") or {})

    for attempt in range(retries + 1):
        try:
            response = requests.request(
                method=method,
                url=endpoint["url"],
                headers=headers or None,
                json=endpoint.get("json"),
                data=endpoint.get("data"),
                timeout=timeout,
                verify=verify_ssl,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - keep one merchant failure isolated.
            last_error = exc
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
            else:
                break
    raise RuntimeError(str(last_error))


def normalize_headers(headers: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        if value is None or value == "":
            continue
        normalized[str(key)] = str(value)
    return normalized


def request_merchant_payload(merchant: dict[str, Any], endpoint: dict[str, Any], request_settings: dict[str, Any]) -> dict[str, Any]:
    parser_name = merchant.get("parser")
    if parser_name == "huoqiangshou" and merchant.get("apprize_endpoint"):
        apprize_endpoint = render_template(merchant["apprize_endpoint"], endpoint.get("_context", {}))
        return {
            "detail": request_json(endpoint, request_settings),
            "apprize": request_json(apprize_endpoint, request_settings),
        }
    return request_json(endpoint, request_settings)


def collect(config: dict[str, Any], game_slug: str | None = None, dry_run: bool = False) -> list[dict[str, Any]]:
    request_settings = config.get("settings", {}).get("request", {})
    default_xizi_uuid = str(config.get("settings", {}).get("default_xizi_uuid") or DEFAULT_XIZI_UUID)
    merchants = config.get("merchants", {})
    records: list[dict[str, Any]] = []
    fetched_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    session = session_for_time(fetched_at)

    for game in enabled_games(config, game_slug):
        merchant_ids = game.get("merchant_ids", {})
        for merchant_key, merchant in merchants.items():
            merchant_name = merchant.get("name", merchant_key)
            if not merchant.get("enabled", True):
                continue

            ids = merchant_ids.get(merchant_key, {})
            game_id = ids.get("game_id") or ids.get("productId") or ids.get("id")
            if not game_id:
                message = "missing game_id"
                LOGGER.warning("%s/%s skipped: %s", merchant_key, game.get("slug"), message)
                records.append(
                    make_error_record(
                        merchant_key=merchant_key,
                        merchant_name=merchant_name,
                        game=game,
                        error=message,
                        fetched_at=fetched_at,
                        session=session,
                        status="skipped",
                    )
                )
                continue

            missing_env = missing_required_env(merchant)
            if missing_env or has_empty_token(merchant):
                message = f"required token is missing: {', '.join(missing_env)}" if missing_env else "required token is missing"
                LOGGER.warning("%s/%s skipped: %s", merchant_key, game.get("slug"), message)
                records.append(
                    make_error_record(
                        merchant_key=merchant_key,
                        merchant_name=merchant_name,
                        game=game,
                        error=message,
                        fetched_at=fetched_at,
                        session=session,
                        status="skipped",
                    )
                )
                continue

            context = {**ids, "game_id": game_id}
            if merchant_key == "hangzhouxizi" and not context.get("uuid"):
                context["uuid"] = default_xizi_uuid
            endpoint = render_template(merchant.get("endpoint", {}), context)
            endpoint["_context"] = context
            parser_name = merchant.get("parser", merchant_key)
            parser = PARSERS.get(parser_name)
            if parser is None:
                records.append(
                    make_error_record(
                        merchant_key=merchant_key,
                        merchant_name=merchant_name,
                        game=game,
                        error=f"unknown parser: {parser_name}",
                        fetched_at=fetched_at,
                        session=session,
                    )
                )
                continue

            if dry_run:
                records.append(
                    make_error_record(
                        merchant_key=merchant_key,
                        merchant_name=merchant_name,
                        game=game,
                        error="dry-run ready; remote API not called",
                        fetched_at=fetched_at,
                        session=session,
                        status="ready",
                    )
                )
                continue

            try:
                raw = request_merchant_payload(merchant, endpoint, request_settings)
                parsed = parser(raw)
                record = {
                    "merchant": merchant_key,
                    "merchant_name": merchant_name,
                    "game_slug": game.get("slug"),
                    "game_name": parsed.game_name or game.get("name"),
                    "item_id": parsed.item_id or str(game_id),
                    "sku_id": parsed.sku_id,
                    "sell_price": parsed.sell_price,
                    "recycle_price": parsed.recycle_price,
                    "currency": parsed.currency,
                    "status": parsed.status,
                    "fetched_at": fetched_at,
                    "session": session,
                    "parser_note": parsed.parser_note,
                }
                if request_settings.get("save_raw_response", False):
                    record["raw_response"] = compact_json(raw)
                records.append(record)
            except Exception as exc:  # noqa: BLE001 - keep one merchant failure isolated.
                LOGGER.exception("%s/%s failed", merchant_key, game.get("slug"))
                records.append(
                    make_error_record(
                        merchant_key=merchant_key,
                        merchant_name=merchant_name,
                        game=game,
                        error=str(exc),
                        fetched_at=fetched_at,
                        session=session,
                    )
                )

    if not dry_run:
        append_prices(config["settings"]["storage"]["prices_json"], persistable_records(records))
    return records
