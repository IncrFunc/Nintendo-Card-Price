from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .aggregation import build_daily_average_series, date_key
from .paths import report_dir
from .storage import configured_price_path, load_price_records
from .trend_chart import PAGE_SIZE as TREND_PAGE_SIZE, render_trend_page
from .utils import write_json

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional PNG output.
    PIL_AVAILABLE = False
    Image = ImageDraw = ImageFont = None  # type: ignore[assignment]


MERCHANT_ORDER = ["laolieren", "huoqiangshou", "hailuo", "mogushijian", "baibiandui", "hangzhouxizi", "buerjia"]
TREND_LOOKBACK_DAYS = 365
FONT_REGULAR_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
FONT_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
TODAY_TABLE_TOP = 204
TODAY_TABLE_BOTTOM = 1342
TODAY_TABLE_PAGE_SIZE = 28
TODAY_MERCHANT_LIMIT = 8


def price_text(record: dict[str, Any] | None) -> str:
    if not record:
        return "-"
    if record.get("status") == "unavailable":
        return "不收别家"
    if record.get("status") != "ok":
        return "-"
    price = record.get("recycle_price")
    if price is None:
        return "-"
    return f"¥{float(price):.0f}"


def today_table_layout(game_count: int) -> dict[str, int]:
    count = max(game_count, 1)
    available = TODAY_TABLE_BOTTOM - TODAY_TABLE_TOP
    row_h = min(42, max(14, available // count))
    return {
        "row_h": row_h,
        "name_font": min(20, max(10, row_h - 6)),
        "price_font": min(19, max(10, row_h - 7)),
        "name_limit": 18 if row_h >= 34 else 14 if row_h >= 24 else 10,
        "stripe_h": max(10, row_h - 4),
    }


def truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)] + "…"


def latest_records_for_date(records: list[dict[str, Any]], target_date: str) -> dict[tuple[str, str], dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        if date_key(record.get("fetched_at", "")) != target_date:
            continue
        key = (record.get("game_slug", ""), record.get("merchant", ""))
        if key not in latest or record.get("fetched_at", "") > latest[key].get("fetched_at", ""):
            latest[key] = record
    return latest


def highest_merchants_for_game(
    latest: dict[tuple[str, str], dict[str, Any]],
    game_slug: str,
    merchant_keys: list[str],
) -> set[str]:
    values: list[tuple[str, float]] = []
    for merchant_key in merchant_keys:
        record = latest.get((game_slug, merchant_key))
        if not record or record.get("status") != "ok" or record.get("recycle_price") is None:
            continue
        values.append((merchant_key, float(record["recycle_price"])))
    if not values:
        return set()
    highest = max(value for _, value in values)
    return {merchant_key for merchant_key, value in values if value == highest}


def visible_merchants(
    config: dict[str, Any],
    latest: dict[tuple[str, str], dict[str, Any]],
) -> list[tuple[str, str]]:
    configured = [(key, config["merchants"][key]["name"]) for key in MERCHANT_ORDER if key in config.get("merchants", {})]
    merchants_with_current_data = {
        merchant_key
        for (_, merchant_key), record in latest.items()
        if record.get("status") in {"ok", "unavailable"}
    }
    if not latest or not merchants_with_current_data:
        return configured
    return [(key, name) for key, name in configured if key in merchants_with_current_data]


def trend_cutoff_date(target_date: str | None) -> str | None:
    if not target_date:
        return None
    return (datetime.fromisoformat(target_date).date() - timedelta(days=TREND_LOOKBACK_DAYS - 1)).isoformat()


def trend_average_series(records: list[dict[str, Any]], game_slug: str, target_date: str | None = None) -> list[tuple[str, str, float]]:
    cutoff = trend_cutoff_date(target_date)
    series = []
    for item in build_daily_average_series(records, game_slug):
        item_date = item["date"]
        if cutoff and item_date < cutoff:
            continue
        if target_date and item_date > target_date:
            continue
        series.append((item_date, item_date[5:], item["avg_price"]))
    return series


def build_today_price_table(config: dict[str, Any], records: list[dict[str, Any]], target_date: str) -> list[dict[str, Any]]:
    latest = latest_records_for_date(records, target_date)
    merchants = visible_merchants(config, latest)
    rows = []
    for game in [game for game in config.get("games", []) if game.get("enabled", True)]:
        prices = []
        merchant_keys = [merchant_key for merchant_key, _ in merchants]
        highest_merchants = highest_merchants_for_game(latest, game["slug"], merchant_keys)
        for merchant_key, merchant_name in merchants:
            record = latest.get((game["slug"], merchant_key))
            prices.append(
                {
                    "merchant": merchant_key,
                    "merchant_name": merchant_name,
                    "display_price": price_text(record),
                    "status": record.get("status") if record else "missing",
                    "recycle_price": record.get("recycle_price") if record else None,
                    "fetched_at": record.get("fetched_at") if record else None,
                    "item_id": record.get("item_id") if record else None,
                    "is_highest": merchant_key in highest_merchants,
                }
            )
        rows.append(
            {
                "date": target_date,
                "game_slug": game.get("slug"),
                "game_name": game.get("name"),
                "platform": game.get("platform"),
                "prices": prices,
            }
        )
    return rows


def build_trend_series(config: dict[str, Any], records: list[dict[str, Any]], target_date: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for game in [game for game in config.get("games", []) if game.get("enabled", True)]:
        rows.append(
            {
                "game_slug": game.get("slug"),
                "game_name": game.get("name"),
                "platform": game.get("platform"),
                "daily_average": [
                    {"date": date, "label": label, "avg_price": avg_price}
                    for date, label, avg_price in trend_average_series(records, game["slug"], target_date)
                ],
            }
        )
    return rows


def svg_text(x: int, y: int, text: str, size: int = 24, weight: int = 400, fill: str = "#172033", anchor: str = "start") -> str:
    escaped = html.escape(text)
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escaped}</text>'


def write_svg(path: Path, body: str, width: int = 1080, height: int = 1440) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#f7f8fb"/>
{body}
</svg>
'''
    path.write_text(svg, encoding="utf-8")


def load_font(size: int, bold: bool = False) -> Any:
    if not PIL_AVAILABLE:
        return None
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_REGULAR_CANDIDATES
    for font_path in candidates:
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()


def png_text(draw: Any, xy: tuple[int, int], text: str, size: int = 24, fill: str = "#172033", bold: bool = False, anchor: str | None = None) -> None:
    draw.text(xy, text, font=load_font(size, bold=bold), fill=fill, anchor=anchor)


def today_column_centers(merchant_count: int) -> tuple[int, list[int]]:
    name_left = 64
    name_right = 408
    count = max(merchant_count, 1)
    price_left = 388 if count >= 7 else 460
    price_right = 1024 if count >= 7 else 988
    column_width = (price_right - price_left) / count
    merchant_centers = [round(price_left + column_width * (idx + 0.5)) for idx in range(merchant_count)]
    return (name_left + name_right) // 2, merchant_centers


def today_highlight_half_width(merchant_count: int) -> int:
    if merchant_count >= 7:
        return 38
    return 40 if merchant_count >= 6 else 46


def generate_today_png(config: dict[str, Any], records: list[dict[str, Any]], target_date: str, output: Path) -> None:
    if not PIL_AVAILABLE:
        return
    games = [game for game in config.get("games", []) if game.get("enabled", True)]
    latest = latest_records_for_date(records, target_date)
    merchants = visible_merchants(config, latest)
    subtitle = target_date
    image = Image.new("RGB", (1080, 1440), "#f7f8fb")
    draw = ImageDraw.Draw(image)
    png_text(draw, (54, 46), "Switch 卡带今日回收价", 38, bold=True)
    png_text(draw, (54, 96), subtitle, 22, "#64748b")
    draw.rounded_rectangle((40, 140, 1040, 1360), radius=18, fill="#ffffff", outline="#e5e7eb", width=1)
    x_name = 64
    merchant_limit = min(len(merchants), TODAY_MERCHANT_LIMIT)
    _, merchant_x = today_column_centers(merchant_limit)
    header_y = 168
    png_text(draw, (x_name, header_y), "卡带", 22, "#334155", bold=True, anchor="lm")
    for idx, (_, merchant_name) in enumerate(merchants[:merchant_limit]):
        png_text(draw, (merchant_x[idx], header_y), merchant_name[:4], 20, "#334155", bold=True, anchor="mm")
    layout = today_table_layout(len(games))
    y = TODAY_TABLE_TOP
    row_h = layout["row_h"]
    for index, _game in enumerate(games):
        if index % 2 == 0:
            stripe_h = layout["stripe_h"]
            draw.rounded_rectangle((52, y - stripe_h // 2, 1028, y + stripe_h // 2), radius=6, fill="#f8fafc")
        y += row_h
    y = TODAY_TABLE_TOP
    merchant_keys = [merchant_key for merchant_key, _ in merchants[:merchant_limit]]
    highlight_half = today_highlight_half_width(merchant_limit)
    for index, game in enumerate(games):
        highest_merchants = highest_merchants_for_game(latest, game["slug"], merchant_keys)
        name = truncate_text(game.get("name", ""), layout["name_limit"])
        png_text(draw, (x_name, y), name, layout["name_font"], anchor="lm")
        for idx, (merchant_key, _) in enumerate(merchants[:merchant_limit]):
            is_highest = merchant_key in highest_merchants
            if is_highest:
                draw.rounded_rectangle((merchant_x[idx] - highlight_half, y - row_h // 2 + 3, merchant_x[idx] + highlight_half, y + row_h // 2 - 3), radius=8, fill="#fef3c7")
            png_text(
                draw,
                (merchant_x[idx], y),
                price_text(latest.get((game["slug"], merchant_key))),
                layout["price_font"],
                "#dc2626" if is_highest else "#0f766e",
                bold=True,
                anchor="mm",
            )
        y += row_h
    png_text(draw, (54, 1382), "说明：高亮为当日最高报价；- 表示暂无页面或未采到价格；不收别家表示该回收商不收外店卡。", 20, "#64748b")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def generate_today_page(config: dict[str, Any], records: list[dict[str, Any]], target_date: str, output: Path) -> None:
    games = [game for game in config.get("games", []) if game.get("enabled", True)]
    latest = latest_records_for_date(records, target_date)
    merchants = visible_merchants(config, latest)
    subtitle = target_date
    parts = [
        svg_text(54, 74, "Switch 卡带今日回收价", 38, 760),
        svg_text(54, 112, subtitle, 22, 500, "#64748b"),
        '<rect x="40" y="140" width="1000" height="1220" rx="18" fill="#ffffff" stroke="#e5e7eb"/>',
    ]
    x_name = 64
    merchant_limit = min(len(merchants), TODAY_MERCHANT_LIMIT)
    _, merchant_x = today_column_centers(merchant_limit)
    header_y = 170
    parts.append(svg_text(x_name, header_y, "卡带", 22, 700, "#334155"))
    for idx, (_, merchant_name) in enumerate(merchants[:merchant_limit]):
        parts.append(svg_text(merchant_x[idx], header_y, merchant_name[:4], 20, 700, "#334155", "middle"))
    layout = today_table_layout(len(games))
    y = TODAY_TABLE_TOP + 28
    row_h = layout["row_h"]
    backgrounds = []
    texts = []
    merchant_keys = [merchant_key for merchant_key, _ in merchants[:merchant_limit]]
    highlight_half = today_highlight_half_width(merchant_limit)
    for index, game in enumerate(games):
        highest_merchants = highest_merchants_for_game(latest, game["slug"], merchant_keys)
        if index % 2 == 0:
            stripe_h = layout["stripe_h"]
            backgrounds.append(f'<rect x="52" y="{y - stripe_h}" width="976" height="{stripe_h}" rx="6" fill="#f8fafc"/>')
        name = truncate_text(game.get("name", ""), layout["name_limit"])
        texts.append(svg_text(x_name, y, name, layout["name_font"], 500))
        for idx, (merchant_key, _) in enumerate(merchants[:merchant_limit]):
            is_highest = merchant_key in highest_merchants
            if is_highest:
                backgrounds.append(f'<rect x="{merchant_x[idx] - highlight_half}" y="{y - row_h + 6}" width="{highlight_half * 2}" height="{max(row_h - 8, 14)}" rx="8" fill="#fef3c7"/>')
            texts.append(
                svg_text(
                    merchant_x[idx],
                    y,
                    price_text(latest.get((game["slug"], merchant_key))),
                    layout["price_font"],
                    700 if is_highest else 650,
                    "#dc2626" if is_highest else "#0f766e",
                    "middle",
                )
            )
        y += row_h
    parts.extend(backgrounds)
    parts.extend(texts)
    parts.append(svg_text(54, 1394, "说明：高亮为当日最高报价；- 表示暂无页面或未采到价格；不收别家表示该回收商不收外店卡。", 20, 400, "#64748b"))
    write_svg(output, "\n".join(parts))


def generate_trend_page(records: list[dict[str, Any]], games: list[dict[str, Any]], page_no: int, output: Path, target_date: str | None = None) -> None:
    end = date.fromisoformat(target_date) if target_date else datetime.now().date()
    rows = [(game["name"], trend_average_series(records, game["slug"], end.isoformat())) for game in games]
    render_trend_page(rows, end, output, font_loader=load_font if PIL_AVAILABLE else None)


def generate_trend_png(records: list[dict[str, Any]], games: list[dict[str, Any]], page_no: int, output: Path, target_date: str | None = None) -> None:
    if not PIL_AVAILABLE:
        return
    end = date.fromisoformat(target_date) if target_date else datetime.now().date()
    rows = [(game["name"], trend_average_series(records, game["slug"], end.isoformat())) for game in games]
    render_trend_page(rows, end, output, image_module=Image, draw_module=ImageDraw, font_loader=load_font)


def generate_report(config: dict[str, Any], target_date: str | None = None) -> list[Path]:
    if target_date is None:
        target_date = datetime.now().date().isoformat()
    games = [game for game in config.get("games", []) if game.get("enabled", True)]
    records = load_price_records(
        configured_price_path(config),
        game_slugs=[str(game.get("slug") or "") for game in games],
        date_from=trend_cutoff_date(target_date),
        date_to=target_date,
    )
    output_dir = report_dir(target_date, config)
    today_json = output_dir / "today_prices.json"
    trend_json = output_dir / "trend_series.json"
    write_json(today_json, build_today_price_table(config, records, target_date))
    write_json(trend_json, build_trend_series(config, records, target_date))
    today_chunks = [games[index : index + TODAY_TABLE_PAGE_SIZE] for index in range(0, len(games), TODAY_TABLE_PAGE_SIZE)] or [[]]
    outputs = [today_json, trend_json]
    for chunk_index, chunk in enumerate(today_chunks, start=1):
        today_svg = output_dir / f"{chunk_index:02d}_today_prices.svg"
        page_config = {**config, "games": chunk}
        outputs.append(today_svg)
        generate_today_page(page_config, records, target_date, today_svg)
        today_png = output_dir / f"{chunk_index:02d}_today_prices.png"
        generate_today_png(page_config, records, target_date, today_png)
        if today_png.exists():
            outputs.append(today_png)
    for idx in range(0, len(games), TREND_PAGE_SIZE):
        page_no = idx // TREND_PAGE_SIZE + len(today_chunks) + 1
        output = output_dir / f"{page_no:02d}_trend.svg"
        generate_trend_page(records, games[idx : idx + TREND_PAGE_SIZE], page_no, output, target_date)
        outputs.append(output)
        png_output = output_dir / f"{page_no:02d}_trend.png"
        generate_trend_png(records, games[idx : idx + TREND_PAGE_SIZE], page_no, png_output, target_date)
        if png_output.exists():
            outputs.append(png_output)
    expected = set(outputs)
    for pattern in ("*_trend.svg", "*_trend.png", "*_today_prices.svg", "*_today_prices.png"):
        for old_output in output_dir.glob(pattern):
            if old_output not in expected:
                old_output.unlink()
    return outputs
