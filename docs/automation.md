# Daily automation

This project can run the whole daily flow with Python only:

- `09:50` collect cartridge prices and build `data/publish/<today>/am/`.
- `15:50` collect again and build `data/publish/<today>/pm/`.
- A random minute from `10:00-10:10` publishes the morning pack to Xiaohongshu.
- A random minute from `16:00-16:10` publishes the afternoon pack to Xiaohongshu.

## First-time setup

Install dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
```

Start a controllable Edge window:

```bash
python main.py xhs-edge
```

Log in to Xiaohongshu Creator Center in that Edge window. Keep this Edge profile logged in.

## Run the daily automation loop

```bash
python main.py auto
```

Run the daily automation loop and the web UI with one command:

```bash
python main.py auto --ui --open-browser
```

Defaults:

```bash
python main.py auto --fetch-time 09:50 --fetch-time 15:50 --publish-time 10:00-10:10 --publish-time 16:00-16:10
```

The process must stay running. If it is closed, scheduled jobs will not run.

## Manual test commands

Run the fetch and publish-pack step immediately:

```bash
python main.py auto-fetch
python main.py auto-fetch --session am
python main.py auto-fetch --session pm
```

Run the Xiaohongshu publish step immediately:

```bash
python main.py auto-publish
python main.py auto-publish --session am
python main.py auto-publish --session pm
```

Upload and fill the Xiaohongshu page without clicking publish:

```bash
python main.py xhs-publish
```

Upload, fill, and click publish:

```bash
python main.py xhs-publish --publish
```

## Notes

- The Xiaohongshu step requires Edge remote debugging on port `9223`.
- If Edge is not running, start it with `python main.py xhs-edge`, then log in.
- The automation picks one random publish minute inside each publish window every day. Use the manual `xhs-publish` command first if you want to inspect the content before enabling the loop.
- Morning outputs are written to `data/reports/<date>/am/` and `data/publish/<date>/am/`.
- Afternoon outputs are written to `data/reports/<date>/pm/` and `data/publish/<date>/pm/`.
