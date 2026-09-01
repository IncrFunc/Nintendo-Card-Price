# data 目录

## 版本库数据

- `games.json`：维护中的游戏、启用状态和商家商品 ID。
- `games.example.json`：公开示例游戏清单，供 `config.example.json` 使用。

## 本地运行数据

- `prices.db`：SQLite 价格数据库，是价格记录的唯一存储。
- `reports/<date>/`：每日价格 JSON、SVG 和 PNG。
- `publish/<date>/`：图片顺序清单和发布文案。
- `exports/`：手动导出的 CSV。
- `charts/`：单游戏 HTML 趋势图。
- `runtime/`：接口诊断、商品 ID 搜索结果和 ADB 截图。

本地运行数据均由 `.gitignore` 排除，可以按需清理并重新生成。价格数据库承载历史数据，生产环境应单独备份。
