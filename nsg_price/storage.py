from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import load_json, write_json


def load_prices(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    data = load_json(path)
    if isinstance(data, list):
        return data
    return data.get("prices", [])


def append_prices(path: str | Path, records: list[dict[str, Any]]) -> None:
    existing = load_prices(path)
    existing.extend(records)
    write_json(path, existing)


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
