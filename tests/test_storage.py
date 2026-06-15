import json

from nsg_price.storage import append_prices, load_prices, migrate_legacy_prices_to_shards, price_shard_path


def test_append_prices_writes_daily_jsonl_shards_without_rewriting_legacy_file(tmp_path):
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
    assert price_shard_path(prices_path, "2026-06-15").exists()
    assert price_shard_path(prices_path, "2026-06-16").exists()
    assert [record["game_slug"] for record in load_prices(prices_path)] == ["legacy", "zelda", "mario", "kirby"]


def test_append_prices_with_no_records_does_not_create_storage(tmp_path):
    prices_path = tmp_path / "prices.json"

    append_prices(prices_path, [])

    assert load_prices(prices_path) == []
    assert not prices_path.exists()
    assert not prices_path.with_suffix("").exists()


def test_migrate_legacy_prices_to_shards_keeps_backup_and_placeholder(tmp_path):
    prices_path = tmp_path / "prices.json"
    prices_path.write_text(
        json.dumps([{"game_slug": "zelda", "fetched_at": "2026-06-15T09:50:00+08:00"}]),
        encoding="utf-8",
    )

    result = migrate_legacy_prices_to_shards(prices_path)

    assert result["migrated"] == 1
    assert price_shard_path(prices_path, "2026-06-15").exists()
    assert json.loads(prices_path.read_text(encoding="utf-8"))["prices"] == []
    assert result["backup"]
    assert load_prices(prices_path)[0]["game_slug"] == "zelda"
