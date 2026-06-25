import json
import sqlite3
from pathlib import Path

from nsg_price.storage import append_prices, configured_price_path, load_price_records, load_prices, migrate_prices_to_database, price_db_path, price_shard_path


def test_append_prices_writes_sqlite_database_and_imports_legacy_file(tmp_path):
    prices_path = tmp_path / "prices.json"
    legacy = [{"game_slug": "legacy", "fetched_at": "2026-06-14T09:50:00+08:00"}]
    prices_path.write_text(json.dumps(legacy), encoding="utf-8")

    append_prices(
        prices_path,
        [
            {"game_slug": "zelda", "fetched_at": "2026-06-15T09:50:00+08:00"},
            {"game_slug": "mario", "fetched_at": "2026-06-15T09:51:00+08:00"},
            {"game_slug": "kirby", "fetched_at": "2026-06-16T15:50:00+08:00"},
        ],
    )

    assert json.loads(prices_path.read_text(encoding="utf-8")) == legacy
    assert price_db_path(prices_path).exists()
    assert not price_shard_path(prices_path, "2026-06-15").exists()
    assert not price_shard_path(prices_path, "2026-06-16").exists()
    assert [record["game_slug"] for record in load_prices(prices_path)] == ["legacy", "zelda", "mario", "kirby"]


def test_append_prices_with_no_records_does_not_create_storage(tmp_path):
    prices_path = tmp_path / "prices.json"

    append_prices(prices_path, [])

    assert load_prices(prices_path) == []
    assert not prices_path.exists()
    assert not price_db_path(prices_path).exists()
    assert not prices_path.with_suffix("").exists()


def test_migrate_legacy_prices_to_database_keeps_backup_and_placeholder(tmp_path):
    prices_path = tmp_path / "prices.json"
    prices_path.write_text(
        json.dumps([{"game_slug": "zelda", "fetched_at": "2026-06-15T09:50:00+08:00"}]),
        encoding="utf-8",
    )

    result = migrate_prices_to_database(prices_path)

    assert result["migrated"] == 1
    assert result["database"] == str(price_db_path(prices_path))
    assert price_db_path(prices_path).exists()
    placeholder = json.loads(prices_path.read_text(encoding="utf-8"))
    assert placeholder["prices"] == []
    assert placeholder["migrated_to"] == str(price_db_path(prices_path))
    assert result["backup"]
    assert load_prices(prices_path)[0]["game_slug"] == "zelda"


def test_migrate_sharded_prices_to_database(tmp_path):
    prices_path = tmp_path / "prices.json"
    shard = price_shard_path(prices_path, "2026-06-15")
    shard.parent.mkdir(parents=True)
    shard.write_text(
        json.dumps({"game_slug": "zelda", "fetched_at": "2026-06-15T09:50:00+08:00"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = migrate_prices_to_database(prices_path)

    assert result["migrated"] == 1
    assert price_db_path(prices_path).exists()
    assert load_prices(prices_path)[0]["game_slug"] == "zelda"


def test_load_price_records_filters_sqlite_rows(tmp_path):
    prices_path = tmp_path / "prices.json"
    append_prices(
        prices_path,
        [
            {"game_slug": "zelda", "status": "ok", "fetched_at": "2026-06-14T09:50:00+08:00"},
            {"game_slug": "zelda", "status": "error", "fetched_at": "2026-06-15T09:50:00+08:00"},
            {"game_slug": "mario", "status": "ok", "fetched_at": "2026-06-15T09:50:00+08:00"},
            {"game_slug": "zelda", "status": "ok", "fetched_at": "2026-06-16T09:50:00+08:00"},
        ],
    )

    records = load_price_records(prices_path, game_slug="zelda", status="ok", date_from="2026-06-15", date_to="2026-06-16")

    assert [record["fetched_at"] for record in records] == ["2026-06-16"]


def test_append_prices_stores_date_only_and_replaces_same_day_game_merchant(tmp_path):
    prices_path = tmp_path / "prices.json"

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
    assert records[0]["fetched_at"] == "2026-06-15"
    assert records[0]["recycle_price"] == 210


def test_append_prices_replaces_existing_timestamped_rows_for_same_day(tmp_path):
    prices_path = tmp_path / "prices.json"
    db_path = price_db_path(prices_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
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
        connection.execute(
            """
            INSERT INTO price_records (fetched_at, merchant, game_slug, status, record_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "2026-06-15T09:50:00+08:00",
                "hangzhouxizi",
                "zelda",
                "ok",
                json.dumps(
                    {
                        "merchant": "hangzhouxizi",
                        "game_slug": "zelda",
                        "status": "ok",
                        "recycle_price": 200,
                        "fetched_at": "2026-06-15T09:50:00+08:00",
                    }
                ),
            ),
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
    assert records[0]["fetched_at"] == "2026-06-15"
    assert records[0]["recycle_price"] == 210


def test_configured_price_path_prefers_clear_storage_key():
    config = {
        "settings": {
            "storage": {
                "prices_path": "data/current.db",
                "prices_json": "data/legacy.json",
            }
        }
    }

    assert configured_price_path(config) == Path("data/current.db")
