import json
import sqlite3
from pathlib import Path

import pytest

from nsg_price.storage import append_prices, configured_price_path, load_price_records, load_prices


def test_append_prices_writes_sqlite_database(tmp_path):
    prices_path = tmp_path / "prices.db"

    append_prices(
        prices_path,
        [
            {"merchant": "a", "game_slug": "zelda", "fetched_at": "2026-06-15T09:50:00+08:00"},
            {"merchant": "a", "game_slug": "mario", "fetched_at": "2026-06-15T09:51:00+08:00"},
        ],
    )

    assert prices_path.exists()
    assert [record["game_slug"] for record in load_prices(prices_path)] == ["zelda", "mario"]
    assert all(record["fetched_at"] == "2026-06-15" for record in load_prices(prices_path))


def test_append_prices_with_no_records_does_not_create_storage(tmp_path):
    prices_path = tmp_path / "prices.db"

    append_prices(prices_path, [])

    assert load_prices(prices_path) == []
    assert not prices_path.exists()


def test_load_price_records_filters_sqlite_rows(tmp_path):
    prices_path = tmp_path / "prices.db"
    append_prices(
        prices_path,
        [
            {"merchant": "a", "game_slug": "zelda", "status": "ok", "fetched_at": "2026-06-14T09:50:00+08:00"},
            {"merchant": "a", "game_slug": "zelda", "status": "error", "fetched_at": "2026-06-15T09:50:00+08:00"},
            {"merchant": "a", "game_slug": "mario", "status": "ok", "fetched_at": "2026-06-15T09:50:00+08:00"},
            {"merchant": "a", "game_slug": "zelda", "status": "ok", "fetched_at": "2026-06-16T09:50:00+08:00"},
        ],
    )

    records = load_price_records(prices_path, game_slug="zelda", status="ok", date_from="2026-06-15", date_to="2026-06-16")

    assert [record["fetched_at"] for record in records] == ["2026-06-16"]


def test_append_prices_replaces_same_day_game_merchant(tmp_path):
    prices_path = tmp_path / "prices.db"
    append_prices(
        prices_path,
        [
            {
                "merchant": "hangzhouxizi",
                "game_slug": "zelda",
                "status": "ok",
                "recycle_price": 200,
                "fetched_at": "2026-06-15T09:50:00+08:00",
            }
        ],
    )
    append_prices(
        prices_path,
        [
            {
                "merchant": "hangzhouxizi",
                "game_slug": "zelda",
                "status": "ok",
                "recycle_price": 210,
                "fetched_at": "2026-06-15T15:50:00+08:00",
            }
        ],
    )

    records = load_price_records(prices_path, date_from="2026-06-15", date_to="2026-06-15")

    assert len(records) == 1
    assert records[0]["recycle_price"] == 210


def test_append_prices_replaces_timestamped_row_for_same_day(tmp_path):
    prices_path = tmp_path / "prices.db"
    with sqlite3.connect(prices_path) as connection:
        connection.execute(
            """
            CREATE TABLE price_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fetched_at TEXT,
                merchant TEXT,
                game_slug TEXT,
                status TEXT,
                record_json TEXT NOT NULL
            )
            """
        )
        old = {
            "merchant": "hangzhouxizi",
            "game_slug": "zelda",
            "status": "ok",
            "recycle_price": 200,
            "fetched_at": "2026-06-15T09:50:00+08:00",
        }
        connection.execute(
            """INSERT INTO price_records (fetched_at, merchant, game_slug, status, record_json)
            VALUES (?, ?, ?, ?, ?)""",
            (old["fetched_at"], old["merchant"], old["game_slug"], old["status"], json.dumps(old)),
        )

    append_prices(
        prices_path,
        [
            {
                "merchant": "hangzhouxizi",
                "game_slug": "zelda",
                "status": "ok",
                "recycle_price": 210,
                "fetched_at": "2026-06-15T15:50:00+08:00",
            }
        ],
    )

    records = load_price_records(prices_path, date_from="2026-06-15", date_to="2026-06-15")
    assert len(records) == 1
    assert records[0]["recycle_price"] == 210


def test_storage_rejects_json_paths():
    with pytest.raises(ValueError, match="must point to a .db file"):
        configured_price_path({"settings": {"storage": {"prices_path": "data/prices.json"}}})

    with pytest.raises(ValueError, match="must point to a .db file"):
        load_prices("data/prices.json")


def test_configured_price_path_uses_database_default():
    assert configured_price_path({}) == Path("data/prices.db")
