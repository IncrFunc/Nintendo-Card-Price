# Linux deployment

This keeps the Windows scripts intact and adds a Linux-friendly path for servers or a desktop Linux box.

## Setup

```bash
cd /opt/Nintendo_Game_Price
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
cp .env.example .env
```

Edit `.env`, `config.json`, and `data/games.json` as usual. Connect an Android phone with USB debugging enabled, keep Xiaohongshu logged in, and verify it:

```bash
python main.py xhs-adb-doctor
```

## Run once

```bash
./scripts/run_fetch.sh
```

Dry run:

```bash
DRY_RUN=1 ./scripts/run_fetch.sh
```

## Run the daily loop with UI

```bash
./scripts/run_auto_linux.sh
```

The default loop collects at `11:50` and publishes once at a random minute from `12:00-12:10` through Android ADB.

Useful environment overrides:

```bash
UI_HOST=0.0.0.0 UI_PORT=8765 ./scripts/run_auto_linux.sh
ADB_DEVICE=2527b8b ./scripts/run_auto_linux.sh
ADB_PATH=/opt/android-sdk/platform-tools/adb ./scripts/run_auto_linux.sh
```

## Browser fallback on Linux

The old browser publisher is still available if you set `PUBLISH_DRIVER=browser`. It needs a real browser with remote debugging on port `9223`.

`python main.py xhs-edge` tries these Linux browser commands automatically:

- `microsoft-edge`
- `microsoft-edge-stable`
- `google-chrome`
- `google-chrome-stable`
- `chromium`
- `chromium-browser`

If your browser is elsewhere:

```bash
python main.py xhs-edge --edge-path /path/to/browser
PUBLISH_DRIVER=browser LAUNCH_EDGE=1 ./scripts/run_auto_linux.sh
```

On a headless server, run this inside a desktop session, VNC session, or `xvfb-run` if the browser build supports it. Log in to Xiaohongshu once in the opened browser profile.

## systemd example

Copy and edit the example service:

```bash
sudo cp scripts/systemd/nintendo-game-price.service.example /etc/systemd/system/nintendo-game-price.service
sudo systemctl daemon-reload
sudo systemctl enable --now nintendo-game-price
```

Check logs:

```bash
journalctl -u nintendo-game-price -f
```

The service example assumes the project lives in `/opt/Nintendo_Game_Price`. Change `WorkingDirectory`, `ExecStart`, and optional `ADB_DEVICE` / `ADB_PATH` environment values if you deploy somewhere else.
