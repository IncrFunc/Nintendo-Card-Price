# Nintendo Game Price

用于采集 Nintendo Switch / Switch 2 实体卡带回收价，生成小红书发布图文，并支持每天两次自动采集和自动发布。

## 安装

```bash
pip install -r requirements.txt
playwright install chromium
copy config.example.json config.json
copy .env.example .env
```

在 `.env` 里维护需要的商家 token。

开发和测试环境额外安装：

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## 一键日常运行

启动自动采集、自动发布和网页管理 UI：

```bash
python main.py auto --ui --launch-edge
```

默认时间：

```text
09:50 采集并生成上午发布包
10:00-10:10 随机一分钟自动发布上午小红书
15:50 采集并生成下午发布包
16:00-16:10 随机一分钟自动发布下午小红书
```

首次使用前，先启动可控 Edge 并登录小红书：

```bash
python main.py xhs-edge
```

## 网页管理 UI

```bash
python main.py ui
```

默认地址：

```text
http://127.0.0.1:8765
```

可以维护游戏、排序、启停游戏、维护商家 ID、搜索补全 ID、启停回收商。

## 手动采集和发布

```bash
python main.py auto-fetch --session am
python main.py auto-fetch --session pm
python main.py auto-publish --session am
python main.py auto-publish --session pm
```

只生成发布包：

```bash
python main.py publish-pack --session am
python main.py publish-pack --session pm
```

只上传到小红书但不点发布：

```bash
python main.py xhs-publish --session am
```

上传并发布：

```bash
python main.py xhs-publish --session am --publish
```

## 数据目录

```text
data/prices.db                    当前 SQLite 原始采集记录数据库
data/prices.json                  旧版原始采集记录（兼容迁移读取）
data/prices/YYYY-MM-DD.jsonl      旧版按日期拆分记录（兼容迁移读取）
data/reports/<date>/am|pm/         上午/下午报表图片
data/publish/<date>/am|pm/         上午/下午发布清单和文案
data/runtime/                      临时诊断输出
logs/automation.log                自动化运行日志
```

`publish` 目录不再复制图片，只保存 `caption.txt` 和 `manifest.json`；图片源统一来自 `reports`，避免重复存储。

新配置使用 `settings.storage.prices_path` 指向当前价格库；旧配置里的 `prices_json` 仍会被兼容读取并自动映射到同名 SQLite 数据库。

## 常用维护命令

```bash
python main.py doctor
python main.py test-api
python main.py search-ids --apply
python main.py add-game --slug game-slug --name "游戏名"
python main.py disable-game --slug game-slug
python main.py enable-game --slug game-slug
```

## 版本

当前版本见 `VERSION`，变更记录见 `CHANGELOG.md`。
