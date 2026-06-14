from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any


def date_key(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10]


def session_for_time(value: str) -> str:
    try:
        hour = datetime.fromisoformat(value).hour
    except ValueError:
        hour_text = value[11:13]
        hour = int(hour_text) if hour_text.isdigit() else 0
    return "am" if hour < 12 else "pm"


def session_label(session: str) -> str:
    return "上午" if session == "am" else "下午" if session == "pm" else session


def record_session(record: dict[str, Any]) -> str:
    session = str(record.get("session") or "").strip().lower()
    if session in {"am", "pm"}:
        return session
    return session_for_time(str(record.get("fetched_at", "")))


def latest_ok_by_day_merchant(records: list[dict[str, Any]], game_slug: str) -> dict[str, dict[str, dict[str, Any]]]:
    latest: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        if record.get("game_slug") != game_slug or record.get("status") != "ok" or record.get("recycle_price") is None:
            continue
        day = date_key(record.get("fetched_at", ""))
        merchant = record.get("merchant") or record.get("merchant_name") or ""
        current = latest[day].get(merchant)
        if current is None or record.get("fetched_at", "") > current.get("fetched_at", ""):
            latest[day][merchant] = record
    return latest


def latest_ok_by_session_merchant(records: list[dict[str, Any]], game_slug: str) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    latest: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        if record.get("game_slug") != game_slug or record.get("status") != "ok" or record.get("recycle_price") is None:
            continue
        key = (date_key(record.get("fetched_at", "")), record_session(record))
        merchant = record.get("merchant") or record.get("merchant_name") or ""
        current = latest[key].get(merchant)
        if current is None or record.get("fetched_at", "") > current.get("fetched_at", ""):
            latest[key][merchant] = record
    return latest


def build_daily_average_series(records: list[dict[str, Any]], game_slug: str) -> list[dict[str, Any]]:
    latest = latest_ok_by_day_merchant(records, game_slug)
    daily = []
    for day, merchant_records in sorted(latest.items()):
        items = list(merchant_records.values())
        prices = [float(item["recycle_price"]) for item in items]
        daily.append(
            {
                "date": day,
                "avg_price": round(mean(prices), 2),
                "merchant_prices": [
                    {
                        "merchant": item.get("merchant_name") or item.get("merchant"),
                        "price": item["recycle_price"],
                        "fetched_at": item.get("fetched_at", ""),
                    }
                    for item in sorted(items, key=lambda item: str(item.get("merchant_name") or item.get("merchant")))
                ],
            }
        )
    return daily


def build_session_average_series(records: list[dict[str, Any]], game_slug: str) -> list[dict[str, Any]]:
    latest = latest_ok_by_session_merchant(records, game_slug)
    series = []
    for (day, session), merchant_records in sorted(latest.items()):
        items = list(merchant_records.values())
        prices = [float(item["recycle_price"]) for item in items]
        series.append(
            {
                "date": day,
                "session": session,
                "label": f"{day[5:]} {session_label(session)}",
                "avg_price": round(mean(prices), 2),
                "merchant_prices": [
                    {
                        "merchant": item.get("merchant_name") or item.get("merchant"),
                        "price": item["recycle_price"],
                        "fetched_at": item.get("fetched_at", ""),
                    }
                    for item in sorted(items, key=lambda item: str(item.get("merchant_name") or item.get("merchant")))
                ],
            }
        )
    return series
