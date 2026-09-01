from __future__ import annotations

import re
from pathlib import Path

from .utils import load_json


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


def body_text_before_tags(main_body: str, tags: list[str]) -> str:
    text = main_body.rstrip()
    if text and tags:
        return f"{text}\n\n"
    return text
