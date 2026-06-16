from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .utils import load_json, write_json


def price_shard_dir(path: str | Path) -> Path:
    path = Path(path)
    if path.suffix:
        return path.with_suffix("")
    return path


def price_shard_path(path: str | Path, day: str) -> Path:
    return price_shard_dir(path) / f"{day}.jsonl"


def price_db_path(path: str | Path) -> Path:
    path = Path(path)
    if path.suffix == ".db":
        return path
    return path.with_suffix(".db")


def configured_price_path(config: dict[str, Any]) -> Path:
    storage = config.get("settings", {}).get("storage", {})
    value = storage.get("prices_path") or storage.get("prices_db") or storage.get("prices_json")
    return Path(value or "data/prices.json")


def _record_day(record: dict[str, Any]) -> str:
    fetched_at = str(record.get("fetched_at") or "")
    try:
        return datetime.fromisoformat(fetched_at).date().isoformat()
    except ValueError:
        return fetched_at[:10] if len(fetched_at) >= 10 else datetime.now().date().isoformat()


def _load_legacy_prices(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.is_dir():
        return []
    data = load_json(path)
    if isinstance(data, list):
        return data
    return data.get("prices", [])


def _load_sharded_prices(path: Path) -> list[dict[str, Any]]:
    shard_dir = price_shard_dir(path)
    if not shard_dir.exists() or not shard_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for shard in sorted(shard_dir.glob("*.jsonl")):
        with shard.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


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


def _record_matches(
    record: dict[str, Any],
    *,
    game_slugs: set[str] | None = None,
    statuses: set[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> bool:
    if game_slugs is not None and str(record.get("game_slug") or "") not in game_slugs:
        return False
    if statuses is not None and str(record.get("status") or "") not in statuses:
        return False
    day = _record_day(record)
    if date_from and day < date_from:
        return False
    if date_to and day > date_to:
        return False
    return True


def _load_db_prices(
    path: Path,
    *,
    game_slugs: set[str] | None = None,
    statuses: set[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    db_path = price_db_path(path)
    if not db_path.exists():
        return []
    with _connect_db(db_path) as connection:
        clauses: list[str] = []
        params: list[Any] = []
        if game_slugs is not None:
            if not game_slugs:
                return []
            placeholders = ", ".join("?" for _ in game_slugs)
            clauses.append(f"game_slug IN ({placeholders})")
            params.extend(sorted(game_slugs))
        if statuses is not None:
            if not statuses:
                return []
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(sorted(statuses))
        if date_from:
            clauses.append("fetched_at >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("fetched_at < ?")
            params.append(_date_upper_bound(date_to))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(f"SELECT record_json FROM price_records{where} ORDER BY id", params).fetchall()
    return [json.loads(row[0]) for row in rows]


def _insert_db_prices(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    with _connect_db(price_db_path(path)) as connection:
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
                for record in records
            ],
        )


def _legacy_file_prices(path: Path) -> list[dict[str, Any]]:
    return _load_legacy_prices(path) + _load_sharded_prices(path)


def _bootstrap_db_from_legacy(path: Path) -> int:
    db_path = price_db_path(path)
    if db_path.exists():
        return 0
    legacy_records = _legacy_file_prices(path)
    if legacy_records:
        _insert_db_prices(path, legacy_records)
    return len(legacy_records)


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
    path = Path(path)
    slug_filter = set(game_slugs or ([] if game_slug is None else [game_slug]))
    status_filter = set(statuses or ([] if status is None else [status]))
    slug_filter_or_none = slug_filter if game_slugs is not None or game_slug is not None else None
    status_filter_or_none = status_filter if statuses is not None or status is not None else None
    db_path = price_db_path(path)
    if db_path.exists():
        return _load_db_prices(
            path,
            game_slugs=slug_filter_or_none,
            statuses=status_filter_or_none,
            date_from=date_from,
            date_to=date_to,
        )
    records = _legacy_file_prices(path)
    if not any([slug_filter_or_none is not None, status_filter_or_none is not None, date_from, date_to]):
        return records
    return [
        record
        for record in records
        if _record_matches(
            record,
            game_slugs=slug_filter_or_none,
            statuses=status_filter_or_none,
            date_from=date_from,
            date_to=date_to,
        )
    ]


def append_prices(path: str | Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    path = Path(path)
    _bootstrap_db_from_legacy(path)
    _insert_db_prices(path, records)


def migrate_prices_to_database(path: str | Path, *, keep_backup: bool = True) -> dict[str, Any]:
    path = Path(path)
    db_path = price_db_path(path)
    if db_path.exists():
        return {"migrated": 0, "database": str(db_path), "backup": None, "shard_dir": str(price_shard_dir(path))}
    legacy_records = _legacy_file_prices(path)
    with _connect_db(db_path):
        pass
    _insert_db_prices(path, legacy_records)
    backup_path: Path | None = None
    if path.exists() and keep_backup:
        backup_path = path.with_name(f"{path.name}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak")
        path.replace(backup_path)
    write_json(
        path,
        {
            "prices": [],
            "migrated_to": str(db_path),
            "legacy_shard_dir": str(price_shard_dir(path)),
            "backup": str(backup_path) if backup_path else None,
            "migrated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return {"migrated": len(legacy_records), "database": str(db_path), "backup": str(backup_path) if backup_path else None, "shard_dir": str(price_shard_dir(path))}


def migrate_legacy_prices_to_shards(path: str | Path, *, keep_backup: bool = True) -> dict[str, Any]:
    return migrate_prices_to_database(path, keep_backup=keep_backup)


def export_csv(json_path: str | Path, csv_dir: str | Path) -> Path:
    records = load_prices(json_path)
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
