# Nintendo Game Price

用于采集 Nintendo Switch / Switch 2 实体卡带回收价，生成小红书发布图文，并支持每天自动采集后通过安卓手机发布到小红书。

## 安装

```bash
pip install -r requirements.txt
copy config.example.json config.json
copy .env.example .env
```

在 `.env` 里维护需要的商家 token。开发和测试环境额外安装：

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## 一键每日运行

先连接开启 USB 调试的安卓手机，并确认小红书已登录：

```bash
python main.py xhs-adb-doctor
```

启动自动采集、自动发布和网页管理 UI：

```bash
python main.py auto --ui
```

默认时间：

```text
11:50 采集并生成当天发布包
12:00-12:10 随机一分钟通过安卓手机发布到小红书
```

如果连接了多台设备，指定设备序列号：

```bash
python main.py auto --ui --device 2527b8b
```

Linux 部署见 `docs/linux.md` 和 `docs/automation.md`；Windows 任务计划脚本仍保留在 `scripts/*.ps1`。

## 网页管理 UI

```bash
python main.py ui
```

默认地址：

```text
http://127.0.0.1:8765
```

可以维护游戏、排序、启停游戏、维护商家 ID、搜索补充 ID、启停回收商。

## 手动采集和发布

```bash
python main.py auto-fetch --session am
python main.py auto-publish --driver adb --session am
```

只生成发布包：

```bash
python main.py publish-pack --session am
```

只在安卓手机上填写小红书但不点发布：

```bash
python main.py xhs-adb-publish --session am
```

填写并发布：

```bash
python main.py xhs-adb-publish --session am --publish
```

浏览器发布仍可用：

```bash
python main.py xhs-edge
python main.py auto --ui --publish-driver browser --launch-edge
```

## 数据目录

```text
data/prices.db                    当前 SQLite 原始采集记录数据库
data/prices.json                  旧版原始采集记录，兼容迁移读取
data/prices/YYYY-MM-DD.jsonl      旧版按日期拆分记录，兼容迁移读取
data/reports/<date>/am|pm/         上午/下午报表图片
data/publish/<date>/am|pm/         上午/下午发布清单和文案
data/runtime/                      临时诊断输出
logs/automation.log                自动化运行日志
```

`publish` 目录不再复制图片，只保存 `caption.txt` 和 `manifest.json`；图片源统一来自 `reports`，避免重复存储。

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
