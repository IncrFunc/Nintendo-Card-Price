from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import enabled_games
from .paths import publish_dir, report_dir
from .utils import load_json


def required_env_status(config: dict[str, Any]) -> dict[str, bool]:
    env_names = sorted({env for merchant in config.get("merchants", {}).values() for env in merchant.get("requires_env", [])})
    return {env: bool(os.getenv(env)) for env in env_names}


def id_coverage(config: dict[str, Any]) -> dict[str, Any]:
    merchants = list(config.get("merchants", {}))
    games = enabled_games(config)
    total_slots = len(games) * len(merchants)
    filled = 0
    missing: list[dict[str, str]] = []
    merchant_counts = {merchant: 0 for merchant in merchants}

    for game in games:
        merchant_ids = game.get("merchant_ids", {})
        for merchant in merchants:
            ids = merchant_ids.get(merchant, {})
            if ids.get("game_id") or ids.get("productId") or ids.get("id"):
                filled += 1
                merchant_counts[merchant] += 1
            else:
                missing.append(
                    {
                        "game_slug": str(game.get("slug", "")),
                        "game_name": str(game.get("name", "")),
                        "merchant": merchant,
                    }
                )
    return {"total_slots": total_slots, "filled": filled, "missing": missing, "merchant_counts": merchant_counts}


def expected_report_files(game_count: int) -> dict[str, list[str]]:
    today_pages = max((game_count + 27) // 28, 1)
    trend_pages = (game_count + 5) // 6
    svg = [f"{page_no:02d}_today_prices.svg" for page_no in range(1, today_pages + 1)]
    png = [f"{page_no:02d}_today_prices.png" for page_no in range(1, today_pages + 1)]
    svg += [f"{page_no:02d}_trend.svg" for page_no in range(today_pages + 1, today_pages + trend_pages + 1)]
    png += [f"{page_no:02d}_trend.png" for page_no in range(today_pages + 1, today_pages + trend_pages + 1)]
    json_files = ["today_prices.json", "trend_series.json"]
    return {"png": png, "svg": svg, "json": json_files}


def report_status(target_date: str | None = None, game_count: int = 0, session: str | None = None) -> dict[str, Any]:
    date = target_date or datetime.now().date().isoformat()
    current_report_dir = report_dir(date)
    if session:
        current_report_dir = current_report_dir / session
    expected = expected_report_files(game_count)
    expected_all = expected["png"] + expected["svg"] + expected["json"]
    existing = {path.name for path in current_report_dir.glob("*")} if current_report_dir.exists() else set()
    return {
        "date": date,
        "report_dir": str(current_report_dir),
        "exists": current_report_dir.exists(),
        "png_count": len([name for name in existing if name.endswith(".png")]),
        "svg_count": len([name for name in existing if name.endswith(".svg")]),
        "json_count": len([name for name in existing if name.endswith(".json")]),
        "expected_png_count": len(expected["png"]),
        "expected_svg_count": len(expected["svg"]),
        "expected_json_count": len(expected["json"]),
        "missing_expected": [name for name in expected_all if name not in existing],
    }


def load_json_or_none(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:  # noqa: BLE001 - diagnostics should report bad artifacts, not crash.
        return None


def manifest_image_paths(manifest: Any) -> list[Path]:
    if not isinstance(manifest, dict):
        return []
    return [Path(item["file"]) for item in manifest.get("images", []) if isinstance(item, dict) and item.get("file")]


def task_readiness(config: dict[str, Any], target_date: str | None = None, session: str | None = None) -> dict[str, Any]:
    games = enabled_games(config)
    game_slugs = {str(game.get("slug", "")) for game in games}
    date = target_date or datetime.now().date().isoformat()
    current_report_dir = report_dir(date, config)
    current_publish_dir = publish_dir(date, config)
    if session:
        current_report_dir = current_report_dir / session
        current_publish_dir = current_publish_dir / session
    today_rows = load_json_or_none(current_report_dir / "today_prices.json")
    trend_rows = load_json_or_none(current_report_dir / "trend_series.json")
    manifest = load_json_or_none(current_publish_dir / "manifest.json")

    today_slugs = {str(row.get("game_slug", "")) for row in today_rows} if isinstance(today_rows, list) else set()
    trend_slugs = {str(row.get("game_slug", "")) for row in trend_rows} if isinstance(trend_rows, list) else set()
    expected = expected_report_files(len(games))
    today_page_count = len([name for name in expected["png"] if "today" in name])
    trend_page_count = len([name for name in expected["png"] if "trend" in name])
    trend_page_capacity = trend_page_count * 6
    today_page_capacity = today_page_count * 28
    manifest_images = manifest_image_paths(manifest)
    manifest_images_exist = bool(manifest_images) and all(path.exists() for path in manifest_images)

    checks = {
        "schedule_has_0950_and_1550": {"ok": {"09:50", "15:50"}.issubset(set(schedule_status(config)))},
        "today_table_covers_enabled_games": {
            "ok": bool(game_slugs) and today_slugs == game_slugs,
            "rows": len(today_rows) if isinstance(today_rows, list) else 0,
            "expected": len(games),
        },
        "trend_data_covers_enabled_games": {
            "ok": bool(game_slugs) and trend_slugs == game_slugs,
            "rows": len(trend_rows) if isinstance(trend_rows, list) else 0,
            "expected": len(games),
        },
        "trend_pages_hold_six_games_each": {
            "ok": trend_page_capacity >= len(games) and trend_page_count == (len(games) + 5) // 6,
            "trend_pages": trend_page_count,
            "capacity": trend_page_capacity,
            "games": len(games),
        },
        "today_pages_hold_28_games_each": {
            "ok": today_page_capacity >= len(games) and today_page_count == max((len(games) + 27) // 28, 1),
            "today_pages": today_page_count,
            "capacity": today_page_capacity,
            "games": len(games),
        },
        "publish_pack_ready": {
            "ok": len(manifest_images) == len(expected["png"]) and manifest_images_exist and (current_publish_dir / "caption.txt").exists() and isinstance(manifest, dict),
            "manifest_images": len(manifest_images),
            "expected_png": len(expected["png"]),
            "dir": str(current_publish_dir),
        },
    }
    return {"date": date, "checks": checks}


def schedule_status(config: dict[str, Any]) -> list[str]:
    settings = config.get("settings", {})
    if settings.get("daily_fetch_times"):
        return list(settings["daily_fetch_times"])
    if settings.get("daily_fetch_time"):
        return [settings["daily_fetch_time"]]
    return ["09:50", "15:50"]


def build_doctor_report(config: dict[str, Any], target_date: str | None = None, session: str | None = None) -> dict[str, Any]:
    games = enabled_games(config)
    return {
        "games_enabled": len(games),
        "merchants_enabled": sum(1 for merchant in config.get("merchants", {}).values() if merchant.get("enabled", True)),
        "daily_fetch_times": schedule_status(config),
        "required_env": required_env_status(config),
        "id_coverage": id_coverage(config),
        "report": report_status(target_date, game_count=len(games), session=session),
        "task_readiness": task_readiness(config, target_date, session=session),
    }


def format_doctor_report(report: dict[str, Any]) -> str:
    coverage = report["id_coverage"]
    env = report["required_env"]
    report_info = report["report"]
    lines = [
        "doctor report",
        f"games_enabled: {report['games_enabled']}",
        f"merchants_enabled: {report['merchants_enabled']}",
        f"daily_fetch_times: {', '.join(report['daily_fetch_times'])}",
        f"id_coverage: {coverage['filled']}/{coverage['total_slots']}",
        "merchant_id_counts: "
        + ", ".join(f"{merchant}={count}" for merchant, count in coverage["merchant_counts"].items()),
    ]
    if env:
        lines.append("required_env: " + ", ".join(f"{name}={'ok' if present else 'missing'}" for name, present in env.items()))
    else:
        lines.append("required_env: none")
    lines.append(
        "report_files: "
        f"date={report_info['date']}, "
        f"png={report_info['png_count']}/{report_info['expected_png_count']}, "
        f"svg={report_info['svg_count']}/{report_info['expected_svg_count']}, "
        f"json={report_info['json_count']}/{report_info['expected_json_count']}, "
        f"dir={report_info['report_dir']}"
    )
    if report_info["missing_expected"]:
        lines.append("missing_report_files: " + ", ".join(report_info["missing_expected"]))
    readiness = report.get("task_readiness", {})
    checks = readiness.get("checks", {})
    if checks:
        ok_count = sum(1 for item in checks.values() if item.get("ok"))
        lines.append(f"task_readiness: {ok_count}/{len(checks)} checks ok")
        for name, item in checks.items():
            status = "ok" if item.get("ok") else "needs_work"
            detail = ", ".join(f"{key}={value}" for key, value in item.items() if key != "ok")
            lines.append(f"  {name}: {status}" + (f" ({detail})" if detail else ""))
    missing = coverage["missing"]
    if missing:
        lines.append("missing_ids:")
        for item in missing[:40]:
            lines.append(f"  {item['merchant']}/{item['game_slug']} ({item['game_name']})")
        if len(missing) > 40:
            lines.append(f"  ... and {len(missing) - 40} more")
    return "\n".join(lines)
