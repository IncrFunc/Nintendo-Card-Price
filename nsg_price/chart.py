from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from .aggregation import build_daily_average_series
from .storage import load_prices


def build_daily_series(records: list[dict[str, Any]], game_slug: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    filtered = [
        record
        for record in records
        if record.get("game_slug") == game_slug and record.get("status") == "ok" and record.get("recycle_price") is not None
    ]
    return build_daily_average_series(records, game_slug), filtered


def generate_chart(config: dict[str, Any], game_slug: str) -> Path:
    storage = config["settings"]["storage"]
    records = load_prices(storage["prices_json"])
    daily, filtered = build_daily_series(records, game_slug)
    if not daily:
        raise ValueError(f"No successful price data found for game: {game_slug}")

    game_name = next((r.get("game_name") for r in filtered if r.get("game_name")), game_slug)
    values = [item["avg_price"] for item in daily]
    current = values[-1]
    high = max(values)
    low = min(values)
    avg = round(mean(values), 2)
    latest_details = daily[-1]["merchant_prices"]

    output_dir = Path(storage["chart_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{game_slug}.html"

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{game_name} 回收价走势</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #f6f7f9;
      color: #172033;
    }}
    .page {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 40px;
    }}
    .top {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 20px;
      align-items: end;
      margin-bottom: 20px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      font-weight: 760;
      letter-spacing: 0;
    }}
    .sub {{
      margin: 0;
      color: #627084;
      font-size: 14px;
    }}
    .current {{
      text-align: right;
    }}
    .current span {{
      display: block;
      color: #627084;
      font-size: 13px;
      margin-bottom: 4px;
    }}
    .current strong {{
      font-size: 36px;
      color: #136f63;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-bottom: 18px;
    }}
    .stat, .panel {{
      background: #fff;
      border: 1px solid #e3e7ee;
      border-radius: 8px;
      box-shadow: 0 10px 28px rgba(24, 35, 52, 0.06);
    }}
    .stat {{
      padding: 14px 16px;
    }}
    .stat label {{
      display: block;
      color: #6b7788;
      font-size: 13px;
      margin-bottom: 6px;
    }}
    .stat strong {{
      font-size: 22px;
    }}
    #chart {{
      height: 480px;
    }}
    .details {{
      margin-top: 18px;
      padding: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: left;
      padding: 12px 10px;
      border-bottom: 1px solid #edf0f4;
    }}
    th {{
      color: #627084;
      font-weight: 650;
    }}
    @media (max-width: 720px) {{
      .top, .stats {{
        grid-template-columns: 1fr;
      }}
      .current {{
        text-align: left;
      }}
      #chart {{
        height: 380px;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="top">
      <div>
        <h1>{game_name} 回收价走势</h1>
        <p class="sub">每天每个回收商取最新回收价，再计算当日商家均价。数据源：data/prices.json + data/prices/*.jsonl</p>
      </div>
      <div class="current">
        <span>当天最新平均价</span>
        <strong>¥{current:.2f}</strong>
      </div>
    </section>
    <section class="stats">
      <div class="stat"><label>最高均价</label><strong>¥{high:.2f}</strong></div>
      <div class="stat"><label>最低均价</label><strong>¥{low:.2f}</strong></div>
      <div class="stat"><label>区间平均</label><strong>¥{avg:.2f}</strong></div>
    </section>
    <section class="panel"><div id="chart"></div></section>
    <section class="panel details">
      <h2>当天各回收商明细</h2>
      <table>
        <thead><tr><th>回收商</th><th>回收价</th><th>采集时间</th></tr></thead>
        <tbody>
          {''.join(f"<tr><td>{item['merchant']}</td><td>¥{float(item['price']):.2f}</td><td>{item['fetched_at']}</td></tr>" for item in latest_details)}
        </tbody>
      </table>
    </section>
  </main>
  <script>
    const daily = {json.dumps(daily, ensure_ascii=False)};
    const chart = echarts.init(document.getElementById('chart'));
    chart.setOption({{
      color: ['#136f63'],
      tooltip: {{
        trigger: 'axis',
        valueFormatter: value => '¥' + Number(value).toFixed(2)
      }},
      grid: {{ left: 64, right: 28, top: 36, bottom: 54 }},
      xAxis: {{
        type: 'category',
        data: daily.map(x => x.date),
        axisLine: {{ lineStyle: {{ color: '#cad1dc' }} }},
        axisLabel: {{ color: '#5c6878' }}
      }},
      yAxis: {{
        type: 'value',
        name: 'CNY',
        axisLabel: {{ formatter: '¥{{value}}', color: '#5c6878' }},
        splitLine: {{ lineStyle: {{ color: '#edf0f4' }} }}
      }},
      series: [{{
        name: '平均回收价',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        lineStyle: {{ width: 4 }},
        areaStyle: {{ opacity: 0.12 }},
        data: daily.map(x => x.avg_price)
      }}]
    }});
    window.addEventListener('resize', () => chart.resize());
  </script>
</body>
</html>
"""
    output.write_text(html, encoding="utf-8")
    return output
