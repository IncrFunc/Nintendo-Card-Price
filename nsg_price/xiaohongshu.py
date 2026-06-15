from __future__ import annotations

import asyncio
import random
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from .paths import publish_dir, runtime_root, today_date
from .publish import normalize_session
from .utils import load_json

PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
BODY_TYPE_DELAY_RANGE = (28, 58)
TAG_TYPE_DELAY_RANGE = (55, 95)


@dataclass(frozen=True)
class XiaohongshuPublishResult:
    status: str
    url: str
    title: str
    image_count: int
    screenshot: Path
    message: str


def caption_parts(caption_path: Path) -> tuple[str, str]:
    caption = caption_path.read_text(encoding="utf-8").strip()
    if not caption:
        raise ValueError(f"empty caption: {caption_path}")
    lines = caption.splitlines()
    title = lines[0].strip()
    body = "\n".join(lines[1:]).strip()
    return title, body


def publish_pack_files(pack_dir: Path) -> tuple[list[Path], Path]:
    if not pack_dir.exists():
        raise FileNotFoundError(f"publish pack not found: {pack_dir}")
    manifest_path = pack_dir / "manifest.json"
    images: list[Path] = []
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        images = [Path(item["file"]) for item in manifest.get("images", []) if item.get("file")]
    if not images:
        images = sorted(pack_dir.glob("*.png"), key=lambda path: path.name)
    if not images:
        raise FileNotFoundError(f"no PNG images found in: {pack_dir}")
    missing = [path for path in images if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing publish images: {', '.join(str(path) for path in missing)}")
    caption_path = pack_dir / "caption.txt"
    if not caption_path.exists():
        raise FileNotFoundError(f"missing caption: {caption_path}")
    return images, caption_path


def split_body_and_tags(body: str) -> tuple[str, list[str]]:
    lines = body.rstrip().splitlines()
    if not lines:
        return "", []
    tag_line_index = next((index for index in range(len(lines) - 1, -1, -1) if lines[index].lstrip().startswith("#")), -1)
    if tag_line_index < 0:
        return body, []
    tag_line = lines[tag_line_index]
    tags = [item.lstrip("#") for item in re.findall(r"#[^\s#]+", tag_line)]
    main_lines = lines[:tag_line_index] + lines[tag_line_index + 1 :]
    return "\n".join(main_lines).strip(), tags


def wait_for_debug_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1):
                return
        except URLError:
            time.sleep(0.4)
    raise TimeoutError(f"Edge remote debugging port is not ready: {url}")


def launch_edge_for_xhs(
    *,
    port: int = 9223,
    profile_dir: str | Path | None = None,
    edge_path: str | Path | None = None,
) -> None:
    profile = Path(profile_dir) if profile_dir else Path.home() / "AppData/Local/Temp/xhs-edge-codex-profile"
    profile.mkdir(parents=True, exist_ok=True)
    executable = Path(edge_path) if edge_path else Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if not executable.exists():
        raise FileNotFoundError(f"Edge executable not found: {executable}")
    args = [
        str(executable),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        PUBLISH_URL,
    ]
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for_debug_port(port)


async def _find_publish_page(browser: Any) -> Any:
    pages = [page for context in browser.contexts for page in context.pages]
    xhs_page = next((page for page in pages if "xiaohongshu.com" in page.url), None)
    if xhs_page is None:
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        xhs_page = await context.new_page()
        await xhs_page.goto(PUBLISH_URL, wait_until="domcontentloaded")
    await xhs_page.bring_to_front()
    return xhs_page


async def _activate_image_tab(page: Any) -> None:
    if "target=image" in page.url and "published=true" not in page.url:
        return
    await page.goto(PUBLISH_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(1200)
    tabs = page.locator(".creator-tab")
    count = await tabs.count()
    for index in range(count):
        tab = tabs.nth(index)
        text = (await tab.inner_text()).strip()
        if "上传图文" in text:
            await tab.evaluate("(element) => element.click()")
            await page.wait_for_timeout(1000)
            return
    link = page.get_by_text("上传图文", exact=True)
    if await link.count():
        await link.first.evaluate("(element) => element.click()")
        await page.wait_for_timeout(1000)
        return
    raise RuntimeError("could not find Xiaohongshu image publish tab")


async def _upload_images(page: Any, images: list[Path]) -> None:
    file_input = page.locator("input[type=file]").first
    await file_input.set_input_files([str(path.resolve()) for path in images])
    await page.wait_for_timeout(5000)


async def _human_type(page: Any, text: str, delay_range: tuple[int, int]) -> None:
    for char in text:
        await page.keyboard.type(char, delay=random.randint(*delay_range))


async def _fill_title_and_body(page: Any, title: str, body: str) -> None:
    main_body, tags = split_body_and_tags(body)
    visible_inputs = page.locator('input[type="text"]:visible')
    if await visible_inputs.count() < 1:
        raise RuntimeError("could not find visible title input")
    title_input = visible_inputs.nth(0)
    await title_input.click(timeout=10000)
    await title_input.fill("", timeout=10000)
    await title_input.fill(title, timeout=10000)

    editor = page.locator(".tiptap.ProseMirror").first
    await editor.click(timeout=10000)
    await page.keyboard.press("Control+A")
    await _human_type(page, main_body, BODY_TYPE_DELAY_RANGE)
    if tags:
        await page.keyboard.press("Enter")
        await page.keyboard.press("Enter")
    for tag in tags:
        await _human_type(page, f"#{tag}", TAG_TYPE_DELAY_RANGE)
        await page.wait_for_timeout(900)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(1200)


async def _click_publish_button(page: Any) -> None:
    await page.evaluate(
        """() => {
          const el = document.querySelector('.publish-page');
          if (el) el.scrollTop = el.scrollHeight;
          window.scrollTo(0, document.body.scrollHeight);
        }"""
    )
    await page.wait_for_timeout(700)

    async def click_visible_button(kind: str) -> bool:
        clicked = await page.evaluate(
            """(kind) => {
              const visible = (r) => r.width > 0 && r.height > 0 && r.y >= 0 && r.y < innerHeight;
              const isRed = (color) => /rgb\\((25[0-5]|24\\d|23\\d),\\s*(0|[1-9]\\d),\\s*(3\\d|4\\d|5\\d|6\\d)\\)/.test(color) || /#?ff2442/i.test(color);
              const disabled = (el, s) => el.disabled || el.getAttribute('aria-disabled') === 'true' || s.pointerEvents === 'none' || Number(s.opacity || 1) < 0.45;
              const candidates = [...document.querySelectorAll('button, [role=button], div, span')]
                .map((el) => {
                  const r = el.getBoundingClientRect();
                  const s = getComputedStyle(el);
                  const text = (el.innerText || el.textContent || '').trim();
                  return { el, r, s, text };
                })
                .filter(({ el, r, s }) => visible(r) && !disabled(el, s));
              let filtered;
              if (kind === 'confirm') {
                filtered = candidates.filter(({ r, s, text }) =>
                  (text === '确认发布' || text === '确定' || text === '继续发布' || text === '发布') &&
                  r.width >= 70 && r.height >= 30 &&
                  (isRed(s.backgroundColor) || r.y > innerHeight * 0.35)
                );
              } else {
                filtered = candidates.filter(({ r, s, text }) =>
                  text === '发布' &&
                  r.width >= 90 && r.width <= 260 &&
                  r.height >= 34 && r.height <= 80 &&
                  r.y > innerHeight * 0.55
                );
              }
              filtered.sort((a, b) => {
                if (kind === 'confirm') {
                  const aExact = a.text === '确认发布' || a.text === '确定' || a.text === '继续发布';
                  const bExact = b.text === '确认发布' || b.text === '确定' || b.text === '继续发布';
                  if (aExact !== bExact) return bExact - aExact;
                }
                return (b.r.y - a.r.y) || (b.r.width * b.r.height - a.r.width * a.r.height);
              });
              const hit = filtered[0];
              if (!hit) return false;
              hit.el.scrollIntoView({ block: 'center', inline: 'center' });
              hit.el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, cancelable: true, view: window }));
              hit.el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
              hit.el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
              hit.el.click();
              return true;
            }""",
            kind,
        )
        return bool(clicked)

    clicked = await click_visible_button("publish")
    if not clicked:
        button_box = await page.evaluate(
        """() => {
          const inViewport = (r) => r.width > 0 && r.height > 0 && r.y >= 0 && r.y < innerHeight;
          const isRed = (color) => /rgb\\((25[0-5]|24\\d|23\\d),\\s*(0|[1-9]\\d),\\s*(3\\d|4\\d|5\\d|6\\d)\\)/.test(color);
          const candidates = [...document.querySelectorAll('button, [role=button], div, span')]
            .map((el) => {
              const r = el.getBoundingClientRect();
              const s = getComputedStyle(el);
              const text = (el.innerText || el.textContent || '').trim();
              return { el, r, s, text };
            })
            .filter(({ r, s }) => inViewport(r) && s.pointerEvents !== 'none')
            .filter(({ r, s, text }) => {
              const publishText = text === '发布' || text.includes('发布');
              const redAction = isRed(s.backgroundColor) && r.width >= 70 && r.height >= 30 && r.y > innerHeight * 0.55;
              return publishText || redAction;
            })
            .sort((a, b) => (b.r.y - a.r.y) || (b.r.width * b.r.height - a.r.width * a.r.height));
          const hit = candidates[0];
          if (!hit) return null;
          return { x: hit.r.x + hit.r.width / 2, y: hit.r.y + hit.r.height / 2, text: hit.text };
        }"""
        )
        if button_box:
            await page.mouse.click(button_box["x"], button_box["y"])
        else:
            # Fallback for the current creator layout: bottom action bar, red publish button.
            viewport = page.viewport_size or {"width": 1700, "height": 840}
            await page.mouse.click(viewport["width"] * 0.5, viewport["height"] - 44)
    await page.wait_for_timeout(2200)
    for _ in range(3):
        if not await click_visible_button("confirm"):
            break
        await page.wait_for_timeout(1800)
    await page.wait_for_timeout(8000)


async def _publish_button_still_visible(page: Any) -> bool:
    return bool(
        await page.evaluate(
            """() => {
              return [...document.querySelectorAll('button, [role=button], div, span')].some((el) => {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                const text = (el.innerText || el.textContent || '').trim();
                return text === '发布' &&
                  r.width >= 90 && r.width <= 260 &&
                  r.height >= 34 && r.height <= 80 &&
                  r.y > innerHeight * 0.55 &&
                  r.width > 0 && r.height > 0 &&
                  s.pointerEvents !== 'none' &&
                  Number(s.opacity || 1) >= 0.45;
              });
            }"""
        )
    )


async def _xhs_publish_async(
    *,
    pack_dir: Path,
    port: int,
    publish: bool,
    screenshot_dir: Path,
) -> XiaohongshuPublishResult:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is required: pip install playwright && playwright install chromium") from exc

    images, caption_path = publish_pack_files(pack_dir)
    title, body = caption_parts(caption_path)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        page = await _find_publish_page(browser)
        await _activate_image_tab(page)
        await _upload_images(page, images)
        await _fill_title_and_body(page, title, body)

        if publish:
            await _click_publish_button(page)
            screenshot = screenshot_dir / "xhs_after_publish.png"
            await page.screenshot(path=str(screenshot), full_page=False)
            if await _publish_button_still_visible(page):
                raise RuntimeError(f"publish click did not complete; bottom publish button is still visible, screenshot={screenshot}")
            status = "published" if "published=true" in page.url else "submitted"
            message = "publish clicked"
        else:
            screenshot = screenshot_dir / "xhs_ready_to_publish.png"
            await page.screenshot(path=str(screenshot), full_page=False)
            status = "ready"
            message = "filled and waiting for manual review"

        result = XiaohongshuPublishResult(
            status=status,
            url=page.url,
            title=title,
            image_count=len(images),
            screenshot=screenshot,
            message=message,
        )
        await browser.close()
        return result


def publish_to_xiaohongshu(
    *,
    config: dict[str, Any] | None = None,
    target_date: str | None = None,
    target_session: str | None = None,
    pack_dir: str | Path | None = None,
    port: int = 9223,
    publish: bool = False,
    launch_edge: bool = False,
    profile_dir: str | Path | None = None,
    edge_path: str | Path | None = None,
) -> XiaohongshuPublishResult:
    date = target_date or today_date()
    session = normalize_session(target_session)
    resolved_pack_dir = Path(pack_dir) if pack_dir else publish_dir(date, config)
    if session and pack_dir is None:
        resolved_pack_dir = resolved_pack_dir / session
    if launch_edge:
        launch_edge_for_xhs(port=port, profile_dir=profile_dir, edge_path=edge_path)
    else:
        wait_for_debug_port(port, timeout=3)
    return asyncio.run(
        _xhs_publish_async(
            pack_dir=resolved_pack_dir,
            port=port,
            publish=publish,
            screenshot_dir=runtime_root(config),
        )
    )
