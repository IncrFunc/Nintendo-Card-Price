from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import publish_dir, report_dir
from .report import generate_report
from .utils import load_json, write_json


def report_date(value: str | None = None) -> str:
    return value or datetime.now().date().isoformat()


def report_pngs(report_path: Path) -> list[Path]:
    return sorted(report_path.glob("*.png"), key=lambda path: path.name)


def summarize_today_prices(today_prices: list[dict[str, Any]]) -> dict[str, int]:
    games_with_price = 0
    ok_count = 0
    unavailable_count = 0
    missing_count = 0
    for row in today_prices:
        has_price = False
        for price in row.get("prices", []):
            status = price.get("status")
            if status == "ok":
                ok_count += 1
                has_price = True
            elif status == "unavailable":
                unavailable_count += 1
            else:
                missing_count += 1
        if has_price:
            games_with_price += 1
    return {
        "game_count": len(today_prices),
        "games_with_price": games_with_price,
        "ok_count": ok_count,
        "unavailable_count": unavailable_count,
        "missing_count": missing_count,
    }


COMMENT_PROMPT = "如有想要记录的卡带请评论哦！"
NO_RECYCLE_NOTICE = "我不做回收，要回收卡带的不要找我！"
CAPTION_TAGS = "#任天堂Switch #Switch卡带 #游戏回收 #二手游戏 #价格记录"


def build_caption(target_date: str, summary: dict[str, int]) -> str:
    return "\n".join(
        [
            f"Switch 卡带回收价记录：{target_date}",
            "",
            "前面为本次各回收商价格总表，后续页面展示回收价走势。",
            "价格仅作记录参考，实际回收价以各平台当时页面为准。",
            COMMENT_PROMPT,
            NO_RECYCLE_NOTICE,
            "",
            CAPTION_TAGS,
        ]
    )


def build_publish_pack(
    config: dict[str, Any],
    *,
    target_date: str | None = None,
    output_root: str | Path | None = None,
    regenerate_report: bool = True,
) -> tuple[Path, list[Path]]:
    date = report_date(target_date)
    if regenerate_report:
        generate_report(config, target_date=date)

    source_report_dir = report_dir(date, config)
    today_path = source_report_dir / "today_prices.json"
    if not today_path.exists():
        raise FileNotFoundError(f"missing report data: {today_path}")

    pngs = report_pngs(source_report_dir)
    if not pngs:
        raise FileNotFoundError(f"missing report PNG files in: {source_report_dir}")

    today_prices = load_json(today_path)
    summary = summarize_today_prices(today_prices)
    output_dir = (Path(output_root) / date) if output_root is not None else publish_dir(date, config)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_entries = [{"order": index, "source": str(source), "file": str(source)} for index, source in enumerate(pngs, start=1)]

    caption_path = output_dir / "caption.txt"
    caption_path.write_text(build_caption(date, summary), encoding="utf-8")
    manifest_path = output_dir / "manifest.json"
    write_json(
        manifest_path,
        {
            "date": date,
            "summary": summary,
            "images": image_entries,
            "caption": str(caption_path),
            "report_dir": str(source_report_dir),
        },
    )
    return output_dir, [caption_path, manifest_path]
