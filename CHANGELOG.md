# Changelog

## 0.3.0 - 2026-09-02

- Reworked daily scheduling to catch up overdue jobs and keep the scheduler responsive during collection.
- Made publishing wait for successful due collections so stale packs are not sent.
- Standardized price persistence on one SQLite `prices_path` and removed JSON/JSONL migration code.
- Enabled TLS certificate verification in the public example configuration.
- Removed browser publishing dependencies, obsolete Windows task scripts, internal planning files, and dead helpers.
- Replaced personal device examples with generic Android placeholders and refreshed the Chinese README.

## 0.2.3 - 2026-06-26

- Added Hangzhou Xizi and Hangzhou Buerjia merchant collection support.
- Fixed Hangzhou Xizi spec pricing by requesting `/api/index/guige` with the product `bianma`.
- Fixed Buerjia recycle pricing to use `box + notaobao`.
- Changed SQLite price records to store date-only `fetched_at` values and replace same-day game/merchant rows on later collections.
- Changed trend reports to use daily averages instead of afternoon-only points.
- Removed browser publishing and time-of-day publish sessions. Reports and publish packs now use date-only directories.

## 0.2.2 - 2026-06-25

- Changed the default daily automation schedule to collect once at 11:50 and publish at a random minute from 12:00-12:10.
- Added Android ADB publishing for the daily Xiaohongshu flow.
- Added ADB options to `auto` and `auto-publish`, plus Linux script/systemd environment overrides.
- Ensured noon publishing uses the latest generated pack.

## 0.2.1 - 2026-06-16

- Fixed daily automation so each due fetch/publish reloads the latest config, allowing games added in the UI to be collected without restarting.
- Added SQLite database filtering helpers and clearer `prices_path` storage config support while keeping `prices_json` compatibility.
- Ignored the live `data/prices.db` database and split test-only dependencies into `requirements-dev.txt`.
- Moved the management UI HTML into a resource file and escaped dynamic chart/UI HTML output.
- Added `mogushijian` to the `search-ids --merchant` CLI choices.

## 0.2.0 - 2026-06-15

- Added price labels to trend chart points so every visible point shows its value.
- Split today's price table into multiple pages when more than 28 games are enabled.
- Added `python main.py auto --ui` to run daily automation and the management UI with one command.
- Added merchant enable/disable controls in the management UI.
- Renamed the Hangzhou Xizi display name to `西子电玩`.
- Added the requested Xiaohongshu caption line: `如有想要记录的卡带请评论哦！`.

## 0.1.0

- Initial collector, report, publish-pack, search-id, management UI, and Xiaohongshu publishing workflow.
