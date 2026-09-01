# Nintendo Game Price

采集 Nintendo Switch / Switch 2 卡带回收价，生成每日价格图片和小红书文案，并通过 ADB 操作安卓手机发布或更替笔记图片。

## 功能

- 从多个回收商接口采集卡带回收价。
- 将每日记录写入 SQLite，按游戏和商家覆盖当天旧记录。
- 生成价格表、趋势图、发布文案和有序图片清单。
- 通过安卓手机上的小红书 App 发布图文。
- 编辑个人主页第一篇笔记，按正确顺序替换旧图片。
- 提供网页管理界面维护游戏、商家商品 ID 和启用状态。

## 环境

- Python 3.11+
- Android Debug Bridge（ADB）
- 已开启 USB 调试并登录小红书的安卓手机

## 安装

```bash
python -m venv .venv
```

Linux：

```bash
. .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
cp .env.example .env
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.json config.json
Copy-Item .env.example .env
```

在 `.env` 中填写商家接口凭证，在 `config.json` 中设置时间、目录和商家参数。`config.json` 默认读取 `data/games.example.json`；日常维护可以改为 `data/games.json`。

## 每日自动化

检查手机连接：

```bash
python main.py xhs-adb-doctor
```

启动采集、发布调度和管理界面：

```bash
python main.py auto --ui
```

默认在 `11:50` 采集价格，并在 `12:00-12:10` 随机选择一分钟发布。调度器会执行已经到期的任务；当采集仍在运行时，发布会等待当次采集成功完成。

同时连接多台设备时，指定 `adb devices` 显示的序列号：

```bash
python main.py auto --ui --device ANDROID_SERIAL
```

管理界面默认地址为 `http://127.0.0.1:8765`。Linux 长期运行方式见 [Linux 部署](docs/linux.md)。

## 手动命令

```bash
# 采集价格并生成当天发布包
python main.py auto-fetch

# 立即发布当天内容
python main.py auto-publish

# 只生成图片清单和文案
python main.py publish-pack

# 填写小红书内容并停在发布页
python main.py xhs-adb-publish

# 填写并点击发布
python main.py xhs-adb-publish --publish
```

## 更替笔记图片

命令默认打开小红书个人主页，编辑最新或置顶的第一篇笔记：

```bash
python main.py xhs-adb-replace-latest-images --submit
```

流程会滑动到图片编辑器末尾添加新图，把旧图删到只剩一张占位图，再进入预览页删除最后一张旧图。保存成功后，脚本会删除传到手机的当天临时照片。

旧笔记图片数量与新图数量不同时，显式指定旧图数量：

```bash
python main.py xhs-adb-replace-latest-images --old-image-count 3 --submit
```

详细说明见 [ADB 小红书发布](docs/adb-xiaohongshu.md)。

## 数据与配置

```text
config.json                       本地运行配置
.env                              本地接口凭证
data/games.json                   维护中的游戏和商家商品 ID
data/games.example.json           公开示例游戏清单
data/prices.db                    SQLite 价格记录
data/reports/<date>/              报告 JSON、SVG 和 PNG
data/publish/<date>/              manifest.json 和 caption.txt
data/runtime/                     ADB 截图和诊断文件
logs/                             自动化日志
```

`.env`、`config.json`、数据库、报告、发布包、运行截图和日志均由 `.gitignore` 排除。公开仓库保留示例配置，实际凭证只进入本地或服务器环境。

默认启用 TLS 证书验证。接口调试期间可以在本地 `config.json` 中显式设置 `settings.request.verify_ssl`。

## 维护

```bash
python main.py doctor
python main.py test-api
python main.py search-ids --apply
python main.py init-games --replace
python main.py add-game --slug game-slug --name "游戏名" --platform "Nintendo Switch"
python main.py disable-game --slug game-slug
python main.py enable-game --slug game-slug
```

开发测试：

```bash
pip install -r requirements-dev.txt
python -m pytest
```

当前版本见 `VERSION`，变更记录见 `CHANGELOG.md`。
