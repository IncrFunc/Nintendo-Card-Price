# data 目录说明

这个目录只保留当前主流程会用到的运行数据。

## 核心真实数据

- `prices.db`：当前原始采集价格数据库，SQLite 格式。
- `prices.json`：旧版价格文件；迁移后只保留占位信息，仍可作为兼容迁移来源。
- `prices/YYYY-MM-DD.jsonl`：旧版按日期拆分价格文件；仍可导入数据库，之后不再作为主写入目标。
- `games.json`：当前维护的游戏清单，包含启停状态和各回收商 `game_id`。
- `games.example.json`：示例游戏清单，配合 `config.example.json` 使用。

## 可再生成内容

- `reports/<date>/`：按日期生成的报表源文件和图片。
- `publish/<date>/`：按发布顺序整理好的文案和 manifest。
- `charts/`：单游戏 HTML 趋势图。

## 诊断与辅助文件

- `runtime/doctor_report.json`：最近一次自检结果。
- `runtime/api_test_results.json`：最近一次真实接口测试结果。
- `runtime/search_id_matches.csv` / `runtime/search_id_matches.json`：直接搜索商家接口得到的候选结果，便于人工复核。

可删除但会自动再生成的内容：`reports/`、`publish/`、`charts/`、`runtime/`。

不要手动改 `prices.db`，除非是在修正明确的错误采集记录。旧 `prices.json` / `prices/*.jsonl` 只用于兼容迁移。
新配置优先使用 `settings.storage.prices_path`；旧配置里的 `prices_json` 仍保留兼容。
