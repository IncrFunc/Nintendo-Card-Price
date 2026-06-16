# Linux deployment

This keeps the Windows scripts intact and adds a Linux-friendly path for servers or a desktop Linux box.

## Setup

```bash
cd /opt/Nintendo_Game_Price
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp config.example.json config.json
cp .env.example .env
```

Edit `.env`, `config.json`, and `data/games.json` as usual.

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

Useful environment overrides:

```bash
UI_HOST=0.0.0.0 UI_PORT=8765 ./scripts/run_auto_linux.sh
LAUNCH_EDGE=1 ./scripts/run_auto_linux.sh
```

## Xiaohongshu browser on Linux

The publish step still needs a real browser with remote debugging on port `9223`.

`python main.py xhs-edge` now tries these Linux browser commands automatically:

- `microsoft-edge`
- `microsoft-edge-stable`
- `google-chrome`
- `google-chrome-stable`
- `chromium`
- `chromium-browser`

If your browser is elsewhere:

```bash
python main.py xhs-edge --edge-path /path/to/browser
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

The service example assumes the project lives in `/opt/Nintendo_Game_Price`. Change `WorkingDirectory` and `ExecStart` if you deploy somewhere else.
