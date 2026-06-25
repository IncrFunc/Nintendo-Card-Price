# Daily automation

This project can run the whole daily flow with one long-running Python command:

- `11:50` collect cartridge prices and build `data/publish/<today>/am/`.
- One random minute from `12:00-12:10` publishes that pack to Xiaohongshu through an Android phone over ADB.

## First-time Android setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Connect the phone with USB debugging enabled, keep Xiaohongshu logged in, and check readiness:

```bash
python main.py xhs-adb-doctor
```

If more than one device is connected, pass the serial shown by `adb devices`:

```bash
python main.py xhs-adb-doctor --device 2527b8b
```

## Run the daily automation loop

One command starts daily collection, the random publish window, and the local management UI:

```bash
python main.py auto --ui
```

The current defaults are equivalent to:

```bash
python main.py auto --ui --fetch-time 11:50 --publish-time 12:00-12:10 --publish-driver adb
```

The process must stay running. If it is closed, scheduled jobs will not run.

## Manual test commands

Run the fetch and publish-pack step immediately:

```bash
python main.py auto-fetch --session am
```

Fill and publish today's pack on Android immediately:

```bash
python main.py auto-publish --driver adb --session am
```

Fill the Android Xiaohongshu post without clicking publish:

```bash
python main.py xhs-adb-publish --session am
```

Fill and click publish:

```bash
python main.py xhs-adb-publish --session am --publish
```

## Browser fallback

The old browser-based publisher is still available:

```bash
python main.py xhs-edge
python main.py auto --ui --publish-driver browser --launch-edge
```

## Notes

- The automation picks one random publish minute inside each publish window every day.
- The noon publish uses the latest fetch session from the same day, so the `12:00-12:10` window publishes the `11:50` `am` pack.
- Android screenshots are written under `data/runtime/adb-xhs/` by default.
