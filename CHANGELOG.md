# Changelog

## 0.2.1 - 2026-06-16

- Fixed daily automation so each due fetch/publish reloads the latest config, allowing games added in the UI to be collected without restarting.
- Added SQLite database filtering helpers and clearer `prices_path` storage config support while keeping `prices_json` compatibility.
- Ignored the live `data/prices.db` database and split test-only dependencies into `requirements-dev.txt`.
- Moved the management UI HTML into a resource file and escaped dynamic chart/UI HTML output.
- Added `mogushijian` to the `search-ids --merchant` CLI choices.

## 0.2.0 - 2026-06-15

- Added morning/afternoon collection sessions (`am` and `pm`) so two daily runs produce separate reports and publish packs.
- Added price labels to trend chart points so every visible point shows its value.
- Split today's price table into multiple pages when more than 28 games are enabled.
- Added `python main.py auto --ui` to run daily automation and the management UI with one command.
- Added merchant enable/disable controls in the management UI.
- Renamed the Hangzhou Xizi display name to `西子电玩`.
- Added the requested Xiaohongshu caption line: `如有想要记录的卡带请评论哦！`.

## 0.1.0

- Initial collector, report, publish-pack, search-id, management UI, and Xiaohongshu publishing workflow.
