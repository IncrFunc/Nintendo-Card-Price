from __future__ import annotations

import csv
import json
from datetime import datetime
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


def load_prices(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    return _load_legacy_prices(path) + _load_sharded_prices(path)


def append_prices(path: str | Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(_record_day(record), []).append(record)
    for day, day_records in grouped.items():
        shard = price_shard_path(path, day)
        shard.parent.mkdir(parents=True, exist_ok=True)
        with shard.open("a", encoding="utf-8") as fp:
            for record in day_records:
                fp.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def migrate_legacy_prices_to_shards(path: str | Path, *, keep_backup: bool = True) -> dict[str, Any]:
    path = Path(path)
    legacy_records = _load_legacy_prices(path)
    if not legacy_records:
        return {"migrated": 0, "shard_dir": str(price_shard_dir(path)), "backup": None}
    append_prices(path, legacy_records)
    backup_path: Path | None = None
    if keep_backup:
        backup_path = path.with_name(f"{path.name}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak")
        path.replace(backup_path)
    write_json(
        path,
        {
            "prices": [],
            "migrated_to": str(price_shard_dir(path)),
            "backup": str(backup_path) if backup_path else None,
            "migrated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    return {"migrated": len(legacy_records), "shard_dir": str(price_shard_dir(path)), "backup": str(backup_path) if backup_path else None}


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
