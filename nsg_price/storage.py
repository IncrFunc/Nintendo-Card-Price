from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def configured_price_path(config: dict[str, Any]) -> Path:
    value = config.get("settings", {}).get("storage", {}).get("prices_path")
    path = Path(value or "data/prices.db")
    if path.suffix.lower() != ".db":
        raise ValueError("settings.storage.prices_path must point to a .db file")
    return path


def _record_day(record: dict[str, Any]) -> str:
    fetched_at = str(record.get("fetched_at") or "")
    try:
        return datetime.fromisoformat(fetched_at).date().isoformat()
    except ValueError:
        return fetched_at[:10] if len(fetched_at) >= 10 else datetime.now().date().isoformat()


def _date_only_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized["fetched_at"] = _record_day(record)
    return normalized


def _connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS price_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fetched_at TEXT,
            merchant TEXT,
            game_slug TEXT,
            status TEXT,
            record_json TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_price_records_fetched_at ON price_records(fetched_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_price_records_game_slug ON price_records(game_slug)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_price_records_merchant ON price_records(merchant)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_price_records_game_status_time ON price_records(game_slug, status, fetched_at)")
    return connection


def _date_upper_bound(value: str) -> str:
    try:
        return (datetime.fromisoformat(value).date() + timedelta(days=1)).isoformat()
    except ValueError:
        return value


def load_prices(path: str | Path) -> list[dict[str, Any]]:
    return load_price_records(path)


def load_price_records(
    path: str | Path,
    *,
    game_slug: str | None = None,
    game_slugs: list[str] | set[str] | tuple[str, ...] | None = None,
    status: str | None = None,
    statuses: list[str] | set[str] | tuple[str, ...] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    database = Path(path)
    if database.suffix.lower() != ".db":
        raise ValueError("price storage path must point to a .db file")
    if not database.exists():
        return []

    slug_filter = set(game_slugs or ([] if game_slug is None else [game_slug]))
    status_filter = set(statuses or ([] if status is None else [status]))
    slug_filter_or_none = slug_filter if game_slugs is not None or game_slug is not None else None
    status_filter_or_none = status_filter if statuses is not None or status is not None else None

    clauses: list[str] = []
    params: list[Any] = []
    for column, values in (("game_slug", slug_filter_or_none), ("status", status_filter_or_none)):
        if values is None:
            continue
        if not values:
            return []
        placeholders = ", ".join("?" for _ in values)
        clauses.append(f"{column} IN ({placeholders})")
        params.extend(sorted(values))
    if date_from:
        clauses.append("fetched_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("fetched_at < ?")
        params.append(_date_upper_bound(date_to))

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect_db(database) as connection:
        rows = connection.execute(f"SELECT record_json FROM price_records{where} ORDER BY id", params).fetchall()
    return [json.loads(row[0]) for row in rows]


def append_prices(path: str | Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    database = Path(path)
    if database.suffix.lower() != ".db":
        raise ValueError("price storage path must point to a .db file")
    normalized_records = [_date_only_record(record) for record in records]
    with _connect_db(database) as connection:
        for record in normalized_records:
            connection.execute(
                """
                DELETE FROM price_records
                WHERE substr(fetched_at, 1, 10) = ? AND merchant = ? AND game_slug = ?
                """,
                (
                    str(record.get("fetched_at") or ""),
                    str(record.get("merchant") or ""),
                    str(record.get("game_slug") or ""),
                ),
            )
        connection.executemany(
            """
            INSERT INTO price_records (fetched_at, merchant, game_slug, status, record_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    str(record.get("fetched_at") or ""),
                    str(record.get("merchant") or ""),
                    str(record.get("game_slug") or ""),
                    str(record.get("status") or ""),
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                )
                for record in normalized_records
            ],
        )


def export_csv(database_path: str | Path, csv_dir: str | Path) -> Path:
    records = load_prices(database_path)
    csv_dir = Path(csv_dir)
    csv_dir.mkdir(parents=True, exist_ok=True)
    output = csv_dir / f"prices-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    fields = [
        "merchant",
        "merchant_name",
        "game_slug",
        "game_name",
        "item_id",
        "sku_id",
        "sell_price",
        "recycle_price",
        "currency",
        "status",
        "fetched_at",
        "error",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})
    return output
