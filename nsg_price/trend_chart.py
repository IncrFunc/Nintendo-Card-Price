from __future__ import annotations

import html
from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any


PAGE_SIZE = 8
WIDTH, HEIGHT = 1080, 1390
X0, X1 = 60, 1016


def previous_month(day: date) -> date:
    year, month_zero = divmod(day.year * 12 + day.month - 2, 12)
    month = month_zero + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def monthly_metrics(series: list[tuple[str, str, float]], end: date) -> tuple[float | None, float | None]:
    if not series:
        return None, None
    cutoff = previous_month(end).isoformat()
    recent = [value for day, _, value in series if day >= cutoff]
    if not recent:
        return None, None
    baseline = next((value for day, _, value in reversed(series) if day <= cutoff), series[0][2])
    change = (series[-1][2] / baseline - 1) * 100 if baseline else None
    return max(recent), change


def render_trend_page(
    rows: list[tuple[str, list[tuple[str, str, float]]]],
    end: date,
    output: Path,
    *,
    image_module: Any = None,
    draw_module: Any = None,
    font_loader: Any = None,
) -> None:
    """Render the same layout to SVG or a supersampled PNG."""
    is_png = output.suffix == ".png"
    scale = 2
    image = image_module.new("RGB", (WIDTH * scale, HEIGHT * scale), "white") if is_png else None
    draw = draw_module.Draw(image) if is_png else None
    parts = ['<rect width="100%" height="100%" fill="#ffffff"/>']

    def text(x: float, y: float, value: str, size: int = 20, color: str = "#737d88", bold: bool = False, anchor: str = "la") -> None:
        if draw is not None:
            draw.text((x * scale, y * scale), value, font=font_loader(size * scale, bold), fill=color, anchor=anchor)
        else:
            horizontal = {"l": "start", "m": "middle", "r": "end"}[anchor[0]]
            baseline = {"a": "hanging", "t": "hanging", "b": "text-after-edge"}[anchor[1]]
            parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{horizontal}" dominant-baseline="{baseline}">{html.escape(value)}</text>')

    def path(points: list[tuple[float, float]], color: str, width: int = 1, fill: bool = False) -> None:
        if draw is not None:
            scaled = [(round(x * scale), round(y * scale)) for x, y in points]
            if fill:
                draw.polygon(scaled, fill=color)
            else:
                draw.line(scaled, fill=color, width=width * scale, joint="curve")
        else:
            coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
            if fill:
                parts.append(f'<polygon points="{coords}" fill="{color}"/>')
            else:
                parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')

    def dot(x: float, y: float, radius: int, fill: str, outline: str | None = None) -> None:
        if draw is not None:
            draw.ellipse(((x-radius)*scale, (y-radius)*scale, (x+radius)*scale, (y+radius)*scale), fill=fill, outline=outline, width=2*scale)
        else:
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}" stroke="{outline or fill}" stroke-width="2"/>')

    start = min((date.fromisoformat(series[0][0]) for _, series in rows if series), default=end)
    days = max((end - start).days, 1)

    def xpos(day: date) -> float:
        return X0 + (day - start).days / days * (X1 - X0)

    ticks = [start]
    month = start.replace(day=1)
    while month <= end:
        if X0 + 65 < xpos(month) < X1 - 65 and xpos(month) - xpos(ticks[-1]) >= 85:
            ticks.append(month)
        year, month_zero = divmod(month.year * 12 + month.month, 12)
        month = date(year, month_zero + 1, 1)
    if end != start:
        ticks.append(end)

    text(48, 30, "卡带价格走势", 42, "#17232c", True)
    text(50, 94, "近一年  /  商家平均回收价", 20)
    text(851, 99, "近一月最高均价", 17, anchor="ra")
    text(1030, 99, "最新均价", 17, anchor="ra")
    text(1032, 43, end.strftime("%Y.%m.%d"), 22, "#17232c", True, "ra")
    path([(48, 140), (1032, 140)], "#26343f", 2)
    for index, (name, series) in enumerate(rows):
        top = 160 + index * 146
        if index % 2:
            path([(32, top-4), (1048, top-4), (1048, top+137), (32, top+137)], "#f7f9fc", fill=True)
        # Reserve the right-hand columns even for unusually long game names.
        name_size = 24
        while name_size > 16 and sum(1 if ord(c) > 127 else .6 for c in name) * name_size > 625:
            name_size -= 1
        if font_loader is not None:
            font = font_loader(name_size * scale, True)
            while name and font.getlength(name) > 625 * scale:
                name = name[:-2] + "…"
        elif len(name) * name_size > 625:
            name = name[:625 // name_size - 1] + "…"
        text(50, top, name, name_size, "#17232c", True)
        high_month, change = monthly_metrics(series, end)
        text(1030, top-3, f"¥{series[-1][2]:.1f}" if series else "暂无", 30, "#17232c", True, "ra")
        text(851, top+3, f"¥{high_month:.1f}" if high_month is not None else "—", 24, "#697b98", anchor="ra")
        if change is not None:
            label = "近一月" if series[0][0] <= previous_month(end).isoformat() else "记录以来"
            text(1030, top+35, f"{label} {change:+.1f}%", 16, "#16806c" if change <= 0 else "#c65255", anchor="ra")
        chart_top, chart_bottom = top+58, top+120
        for tick in ticks:
            x = xpos(tick)
            for y in range(chart_top, chart_bottom, 7):
                path([(x, y), (x, y+2)], "#dfe5ed")
        if series:
            values = [value for _, _, value in series]
            low, high = min(values), max(values)
            span = max(high-low, 5)
            ymin, ymax = low-span*.10, high+span*.13
            points = [(xpos(date.fromisoformat(day)), chart_bottom-(value-ymin)/(ymax-ymin)*(chart_bottom-chart_top)) for day, _, value in series]
            path([*points, (points[-1][0], chart_bottom), (points[0][0], chart_bottom)], "#eaf0fc", fill=True)
            if len(points) > 1:
                path(points, "#426abd", 3)
            marked: list[float] = []
            for idx, word in ((values.index(high), "高"), (values.index(low), "低")):
                x, y = points[idx]
                if any(abs(x-prev) < 95 for prev in marked):
                    continue
                marked.append(x)
                dot(x, y, 3, "white", "#426abd")
                above = y < top+85
                text(max(90, min(x, 970)), y-7 if above else y+7, f"{word} {values[idx]:.0f}", 15, "#697b98", anchor="mb" if above else "mt")
            dot(*points[-1], 4, "#426abd")
        else:
            text(538, top+80, "暂无历史价格", 18, anchor="ma")
        path([(48, top+137), (1032, top+137)], "#e5e9ef")
    for tick in ticks:
        text(xpos(tick), 1341, tick.strftime("%m/%d"), 17, anchor="ma")
    output.parent.mkdir(parents=True, exist_ok=True)
    if image is not None:
        image.resize((WIDTH, HEIGHT), image_module.Resampling.LANCZOS).save(output)
    else:
        body = "\n".join(parts)
        output.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">\n{body}\n</svg>\n', encoding="utf-8")
