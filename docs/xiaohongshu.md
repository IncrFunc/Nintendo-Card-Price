# Xiaohongshu publish script

Build the publish pack first:

```bash
python main.py publish-pack
```

Launch a controllable Edge window, then log in to Xiaohongshu Creator Center in that window:

```bash
python main.py xhs-edge
```

After login, run the upload flow. By default it uploads images and fills title/body, but does not click the final publish button:

```bash
python main.py xhs-publish
python main.py xhs-publish --date 2026-06-14
python main.py xhs-publish --date 2026-06-14 --session pm
```

After reviewing the preview, add `--publish` to click the final publish button:

```bash
python main.py xhs-publish --publish
python main.py xhs-publish --session am --publish
```

If Playwright is not installed:

```bash
pip install -r requirements.txt
playwright install chromium
```

Useful options:

```bash
python main.py xhs-publish --port 9223
python main.py xhs-publish --pack-dir data/publish/2026-06-14/pm
python main.py xhs-publish --launch-edge --profile-dir C:\temp\xhs-edge-profile
```

Publish packs no longer duplicate PNG files. `manifest.json` points to the source images under `data/reports/<date>/<session>/`, and the uploader reads those paths directly.
