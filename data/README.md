# data 目录说明

这个目录现在只保留当前主流程真正会用到的内容。历史离线 `id` 表扫描链路已经移除，项目只保留“直接搜索商家接口并写入 `game_id`”这条主线。

- 核心真数据
- `prices.json`：历史采集价格，报表和走势图都从这里读取。
- `games.json`：当前维护的游戏清单，包含启停状态和各回收商 `game_id`。
- `games.example.json`：示例游戏清单，配合 `config.example.json` 使用。

- 可再生产物
- `reports/<date>/`：按日期生成的报表源文件和图片。
- `publish/<date>/`：按发布顺序整理好的图片、文案和 manifest。
- `charts/`：单游戏 HTML 走势图。

- 诊断与辅助文件
- `runtime/doctor_report.json`：最近一次自检结果。
- `runtime/api_test_results.json`：最近一次真实接口测试结果。
- `runtime/search_id_matches.csv` / `runtime/search_id_matches.json`：直接搜索商家接口得到的候选结果，便于人工复核。
- `xizi_api_probe.json`：杭州西子接口探测记录。

可删除但会自动再生成的内容：`reports/`、`publish/`、`charts/`、`runtime/`。

不要手动改 `prices.json`，除非是在修正明确的错误采集记录。
