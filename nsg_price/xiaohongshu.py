from __future__ import annotations

import asyncio
import random
import re
import shutil
import subprocess
import sys
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
TITLE_TYPE_DELAY_RANGE = (1500, 2500)
BODY_PASTE_DELAY_RANGE = (900, 1800)
TAG_TYPE_DELAY_RANGE = (1500, 2500)
PUNCTUATION_PAUSE_RANGE = (180, 420)
LINE_BREAK_DELAY_RANGE = (220, 520)
CLICK_DELAY_RANGE = (350, 1200)
UPLOAD_PICKER_DELAY_RANGE = (1500, 3200)
UPLOAD_SETTLE_PER_IMAGE_DELAY_RANGE = (900, 1800)
OPEN_BEFORE_UPLOAD_MS = 20000
AFTER_UPLOAD_BEFORE_COPY_MS = 10000
TAG_INTERVAL_MS = 1000
EDIT_MINIMUM_DURATION_MS = 180000
LINUX_BROWSER_CANDIDATES = (
    "microsoft-edge",
    "microsoft-edge-stable",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)


@dataclass(frozen=True)
class XiaohongshuPublishResult:
    status: str
    url: str
    title: str
    image_count: int
    screenshot: Path
    message: str
    before_publish_screenshot: Path | None = None


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


def publish_screenshot_dir(pack_dir: Path, fallback_dir: Path) -> Path:
    manifest_path = pack_dir / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        report_path = manifest.get("report_dir")
        if report_path:
            return Path(report_path)
    return fallback_dir


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


def default_xhs_profile_dir() -> Path:
    if sys.platform.startswith("win"):
        return Path.home() / "AppData/Local/Temp/xhs-edge-codex-profile"
    return Path.home() / ".cache/nintendo-game-price/xhs-browser-profile"


def find_xhs_browser_executable(edge_path: str | Path | None = None) -> Path:
    if edge_path:
        executable = Path(edge_path)
        if executable.exists():
            return executable
        raise FileNotFoundError(f"browser executable not found: {executable}")

    windows_edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if sys.platform.startswith("win"):
        if windows_edge.exists():
            return windows_edge
        resolved = shutil.which("msedge") or shutil.which("microsoft-edge")
        if resolved:
            return Path(resolved)
        raise FileNotFoundError(f"Edge executable not found: {windows_edge}")

    for name in LINUX_BROWSER_CANDIDATES:
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)
    raise FileNotFoundError("Linux browser executable not found: install Microsoft Edge, Google Chrome, or Chromium, or pass --edge-path")


def launch_edge_for_xhs(
    *,
    port: int = 9223,
    profile_dir: str | Path | None = None,
    edge_path: str | Path | None = None,
) -> None:
    profile = Path(profile_dir) if profile_dir else default_xhs_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    executable = find_xhs_browser_executable(edge_path)
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
            box = await tab.bounding_box()
            if not box or box["x"] < 0 or box["y"] < 0:
                continue
            await _human_click_locator(page, tab)
            await page.wait_for_timeout(1000)
            return
    link = page.get_by_text("上传图文", exact=True)
    count = await link.count()
    for index in range(count):
        candidate = link.nth(index)
        box = await candidate.bounding_box()
        if not box or box["x"] < 0 or box["y"] < 0:
            continue
        await _human_click_locator(page, candidate)
        await page.wait_for_timeout(1000)
        return
    raise RuntimeError("could not find Xiaohongshu image publish tab")


async def _human_click_locator(page: Any, locator: Any, *, timeout: int = 10000) -> None:
    await locator.wait_for(state="visible", timeout=timeout)
    await locator.scroll_into_view_if_needed(timeout=timeout)
    box = await locator.bounding_box(timeout=timeout)
    if not box:
        await locator.click(timeout=timeout)
        return
    padding_x = min(10, max(box["width"] / 4, 0))
    padding_y = min(10, max(box["height"] / 4, 0))
    min_x = box["x"] + padding_x
    max_x = box["x"] + max(box["width"] - padding_x, padding_x)
    min_y = box["y"] + padding_y
    max_y = box["y"] + max(box["height"] - padding_y, padding_y)
    x = random.uniform(min_x, max_x)
    y = random.uniform(min_y, max_y)
    await page.mouse.move(x + random.uniform(-2, 2), y + random.uniform(-2, 2), steps=random.randint(4, 9))
    await _human_wait(page, CLICK_DELAY_RANGE)
    await page.mouse.click(x, y, delay=random.randint(40, 160))


async def _random_mouse_click(page: Any, x: float, y: float, *, radius: float = 8) -> None:
    target_x = x + random.uniform(-radius, radius)
    target_y = y + random.uniform(-radius, radius)
    await page.mouse.move(target_x + random.uniform(-2, 2), target_y + random.uniform(-2, 2), steps=random.randint(4, 9))
    await _human_wait(page, CLICK_DELAY_RANGE)
    await page.mouse.click(target_x, target_y, delay=random.randint(40, 160))


async def _click_upload_entry(page: Any) -> None:
    selectors = [
        "text=上传图片",
        "text=上传图文",
        "text=选择图片",
        ".upload-wrapper",
        ".upload-box",
        ".upload-container",
        ".image-upload",
        ".upload",
        "input[type=file]",
    ]
    for selector in selectors:
        locator = page.locator(selector).first
        if await locator.count():
            try:
                await _human_click_locator(page, locator, timeout=3000)
                return
            except Exception:
                continue
    raise RuntimeError("could not find Xiaohongshu image upload entry")


async def _upload_images(page: Any, images: list[Path]) -> None:
    await _human_wait(page, UPLOAD_PICKER_DELAY_RANGE)
    async with page.expect_file_chooser(timeout=15000) as chooser_info:
        await _click_upload_entry(page)
    file_chooser = await chooser_info.value
    await file_chooser.set_files([str(path.resolve()) for path in images])
    await page.wait_for_timeout(AFTER_UPLOAD_BEFORE_COPY_MS)
    for _ in images:
        await _human_wait(page, UPLOAD_SETTLE_PER_IMAGE_DELAY_RANGE)


async def _human_wait(page: Any, delay_range: tuple[int, int]) -> None:
    await page.wait_for_timeout(random.randint(*delay_range))


async def _human_type(page: Any, text: str, delay_range: tuple[int, int]) -> None:
    for char in text:
        if char == "\n":
            await page.keyboard.press("Enter")
            await _human_wait(page, LINE_BREAK_DELAY_RANGE)
            continue
        await page.keyboard.insert_text(char)
        await _human_wait(page, delay_range)
        if char in "。！？!?；;":
            await _human_wait(page, PUNCTUATION_PAUSE_RANGE)


async def _paste_text(page: Any, text: str) -> None:
    await _human_wait(page, BODY_PASTE_DELAY_RANGE)
    try:
        await page.evaluate("async (value) => navigator.clipboard.writeText(value)", text)
        await page.keyboard.press("Control+V")
    except Exception:
        await page.keyboard.insert_text(text)


async def _wait_for_minimum_edit_duration(page: Any, started_at: float) -> None:
    elapsed_ms = int((time.monotonic() - started_at) * 1000)
    remaining_ms = EDIT_MINIMUM_DURATION_MS - elapsed_ms
    if remaining_ms > 0:
        await page.wait_for_timeout(remaining_ms)


async def _insert_text(page: Any, text: str) -> None:
    await page.keyboard.insert_text(text)


async def _fill_title_and_body(page: Any, title: str, body: str) -> None:
    edit_started_at = time.monotonic()
    main_body, tags = split_body_and_tags(body)
    visible_inputs = page.locator('input[type="text"]:visible')
    if await visible_inputs.count() < 1:
        raise RuntimeError("could not find visible title input")
    title_input = visible_inputs.nth(0)
    await _human_click_locator(page, title_input)
    await title_input.fill("", timeout=10000)
    await _human_type(page, title, TITLE_TYPE_DELAY_RANGE)

    editor = page.locator(".tiptap.ProseMirror").first
    await _human_click_locator(page, editor)
    await page.keyboard.press("Control+A")
    await _paste_text(page, main_body)
    if tags:
        await page.keyboard.press("Enter")
        await page.keyboard.press("Enter")
    for tag in tags:
        await _human_type(page, f"#{tag}", TAG_TYPE_DELAY_RANGE)
        await page.wait_for_timeout(TAG_INTERVAL_MS)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(TAG_INTERVAL_MS)
    await _wait_for_minimum_edit_duration(page, edit_started_at)
    await page.wait_for_timeout(1200)


async def _dispatch_xhs_publish_event(page: Any) -> bool:
    return bool(
        await page.evaluate(
            """() => {
              const buttons = [...document.querySelectorAll('xhs-publish-btn')];
              const button = buttons.find((el) => {
                const rect = el.getBoundingClientRect();
                return el.getAttribute('is-publish') === 'true' &&
                  el.getAttribute('submit-disabled') !== 'true' &&
                  rect.width > 0 &&
                  rect.height > 0;
              });
              if (!button) return false;
              button.dispatchEvent(new CustomEvent('publish', { bubbles: true, composed: true }));
              return true;
            }"""
        )
    )


async def _click_publish_button(page: Any) -> None:
    await page.evaluate(
        """() => {
          const el = document.querySelector('.publish-page');
          if (el) el.scrollTop = el.scrollHeight;
          window.scrollTo(0, document.body.scrollHeight);
        }"""
    )
    await page.wait_for_timeout(700)

    if await _dispatch_xhs_publish_event(page):
        await page.wait_for_timeout(3500)
        if "published=true" in page.url:
            return

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
            await _random_mouse_click(page, button_box["x"], button_box["y"])
        else:
            # Fallback for the current creator layout: bottom action bar, red publish button.
            viewport = page.viewport_size or {"width": 1700, "height": 840}
            await _random_mouse_click(page, viewport["width"] * 0.5, viewport["height"] - 44, radius=12)
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
              const xhsButton = [...document.querySelectorAll('xhs-publish-btn')].some((el) => {
                const r = el.getBoundingClientRect();
                return el.getAttribute('is-publish') === 'true' &&
                  el.getAttribute('submit-disabled') !== 'true' &&
                  r.width > 0 &&
                  r.height > 0 &&
                  r.y < innerHeight;
              });
              if (xhsButton) return true;
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
        await page.wait_for_timeout(OPEN_BEFORE_UPLOAD_MS)
        await _upload_images(page, images)
        await _fill_title_and_body(page, title, body)
        before_publish_screenshot = screenshot_dir / "xhs_before_publish.png"
        await page.screenshot(path=str(before_publish_screenshot), full_page=False)

        if publish:
            await _click_publish_button(page)
            screenshot = screenshot_dir / "xhs_after_publish.png"
            await page.screenshot(path=str(screenshot), full_page=False)
            if await _publish_button_still_visible(page):
                raise RuntimeError(f"publish click did not complete; bottom publish button is still visible, screenshot={screenshot}")
            status = "published" if "published=true" in page.url else "submitted"
            message = "publish clicked"
        else:
            screenshot = before_publish_screenshot
            status = "ready"
            message = "filled and waiting for manual review"

        result = XiaohongshuPublishResult(
            status=status,
            url=page.url,
            title=title,
            image_count=len(images),
            screenshot=screenshot,
            message=message,
            before_publish_screenshot=before_publish_screenshot,
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
            screenshot_dir=publish_screenshot_dir(resolved_pack_dir, runtime_root(config)),
        )
    )
