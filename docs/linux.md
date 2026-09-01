# Linux 部署

Linux 部署用于服务器或桌面 Linux 环境。每日发布通过 Android 手机和 ADB 完成。

## 安装

```bash
cd /opt/Nintendo_Game_Price
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
cp .env.example .env
```

按需编辑 `.env`、`config.json` 和 `data/games.json`。连接已开启 USB 调试的 Android 手机，保持小红书登录，然后检查设备：

```bash
python main.py xhs-adb-doctor
```

如果 `adb` 不在 `PATH` 中，显式传入路径：

```bash
python main.py xhs-adb-doctor --adb-path /opt/android-sdk/platform-tools/adb
```

## 单次采集

```bash
./scripts/run_fetch.sh
```

只做 dry run：

```bash
DRY_RUN=1 ./scripts/run_fetch.sh
```

## 启动每日循环和 UI

```bash
./scripts/run_auto_linux.sh
```

默认循环会在 `11:50` 采集，并在 `12:00-12:10` 之间随机一分钟通过 Android ADB 发布。

常用环境变量：

```bash
UI_HOST=0.0.0.0 UI_PORT=8765 ./scripts/run_auto_linux.sh
ADB_DEVICE=ANDROID_SERIAL ./scripts/run_auto_linux.sh
ADB_PATH=/opt/android-sdk/platform-tools/adb ./scripts/run_auto_linux.sh
ADB_OUTPUT_DIR=/var/tmp/nintendo-game-price-adb ./scripts/run_auto_linux.sh
```

## 手动发布测试

```bash
python main.py publish-pack
python main.py xhs-adb-publish
```

正式发布：

```bash
python main.py xhs-adb-publish --publish
```

## systemd 示例

复制并按实际路径编辑示例服务：

```bash
sudo cp scripts/systemd/nintendo-game-price.service.example /etc/systemd/system/nintendo-game-price.service
sudo systemctl daemon-reload
sudo systemctl enable --now nintendo-game-price
```

查看日志：

```bash
journalctl -u nintendo-game-price -f
```

示例服务默认项目目录为 `/opt/Nintendo_Game_Price`。如果部署到其他目录，请修改 `WorkingDirectory`、`ExecStart`，以及可选的 `ADB_DEVICE` / `ADB_PATH` 环境变量。
