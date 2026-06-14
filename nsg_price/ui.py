from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import load_config, save_config
from .config_tools import add_game, remove_game, set_id, update_game
from .search_ids import apply_search_matches, build_search_matches


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Switch 回收价游戏管理</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #ebe7df;
      --shell: #13212f;
      --shell-soft: #1c3144;
      --panel: #fffdf9;
      --panel-tint: #f4efe6;
      --line: #d7ccbc;
      --line-strong: #c0b29f;
      --text: #18212b;
      --muted: #6b6d72;
      --accent: #b35c2e;
      --accent-dark: #93451d;
      --accent-soft: #f8dfcf;
      --info: #2e5b9a;
      --info-soft: #dde8fb;
      --warn: #a33d24;
      --warn-soft: #fae2da;
      --ok: #246a47;
      --ok-soft: #ddf2e4;
      --shadow: 0 18px 40px rgba(46, 33, 18, .12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      font-size: 14px;
      letter-spacing: 0;
      background-image:
        radial-gradient(circle at top left, rgba(255,255,255,.55), transparent 28%),
        linear-gradient(135deg, #ece7de 0%, #e7e1d7 52%, #efeae2 100%);
    }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      display: grid;
      gap: 12px;
      padding: 18px 24px 18px;
      border-bottom: 1px solid rgba(255,255,255,.14);
      background: rgba(19, 33, 47, .94);
      backdrop-filter: blur(12px);
      color: #f6efe6;
      box-shadow: 0 10px 26px rgba(19, 33, 47, .24);
    }
    .hero {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }
    h1 {
      margin: 0;
      font-size: 28px;
      line-height: 1.2;
      letter-spacing: .02em;
    }
    .hero p {
      margin: 6px 0 0;
      color: rgba(246, 239, 230, .7);
      font-size: 13px;
      max-width: 680px;
    }
    .hero-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .overview {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      padding: 16px 18px;
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 18px;
      background:
        linear-gradient(145deg, rgba(255,255,255,.1), rgba(255,255,255,.04)),
        linear-gradient(120deg, rgba(179,92,46,.18), rgba(46,91,154,.12));
    }
    .overview-title {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 6px;
    }
    .overview-name {
      font-size: 20px;
      font-weight: 760;
    }
    .overview-sub {
      color: rgba(246, 239, 230, .74);
      font-size: 13px;
    }
    .stat-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    main {
      display: grid;
      grid-template-columns: minmax(310px, 380px) minmax(0, 1fr);
      min-height: calc(100vh - 144px);
      height: calc(100vh - 144px);
    }
    aside {
      border-right: 1px solid rgba(255,255,255,.08);
      background:
        linear-gradient(180deg, rgba(19,33,47,.98) 0%, rgba(24,45,61,.98) 100%),
        radial-gradient(circle at top, rgba(179,92,46,.16), transparent 22%);
      padding: 20px;
      overflow: auto;
      color: #f4ede4;
      height: 100%;
    }
    section {
      padding: 26px 24px 30px;
      overflow: auto;
      height: 100%;
    }
    .toolbar, .row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .toolbar { margin-bottom: 12px; }
    input, select {
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 9px 12px;
      background: rgba(255,255,255,.92);
      color: var(--text);
      font: inherit;
      transition: border-color .16s ease, box-shadow .16s ease, background .16s ease;
    }
    input:focus, select:focus {
      outline: none;
      border-color: rgba(179, 92, 46, .65);
      box-shadow: 0 0 0 4px rgba(179, 92, 46, .12);
      background: #fff;
    }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.25;
    }
    button {
      min-height: 40px;
      border: 1px solid rgba(24, 33, 43, .12);
      border-radius: 999px;
      padding: 9px 14px;
      background: rgba(255,255,255,.9);
      color: var(--text);
      font: inherit;
      cursor: pointer;
      transition: transform .14s ease, box-shadow .14s ease, background .14s ease, border-color .14s ease;
    }
    button:hover { transform: translateY(-1px); box-shadow: 0 10px 20px rgba(24, 33, 43, .09); }
    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }
    button.primary:hover { background: var(--accent-dark); }
    button.danger {
      border-color: #f0b4ae;
      color: var(--warn);
    }
    button:disabled {
      cursor: not-allowed;
      opacity: .6;
    }
    .sidebar-top {
      display: grid;
      gap: 8px;
      margin-bottom: 10px;
    }
    .sidebar-top .panel {
      margin-bottom: 0;
      padding: 12px;
      border-radius: 18px;
      box-shadow: none;
    }
    .sidebar-top .panel-note {
      display: none;
    }
    .sidebar-top .toolbar {
      margin: 8px 0 0 !important;
    }
    .merchant-switch-panel {
      border-color: rgba(240, 194, 164, .5);
      background: linear-gradient(145deg, rgba(255,253,249,.98), rgba(248,223,207,.92));
      color: var(--text);
      padding: 0;
    }
    .merchant-switch-panel summary {
      display: grid;
      gap: 4px;
      cursor: pointer;
      list-style: none;
      padding: 12px 14px;
    }
    .merchant-switch-panel summary::-webkit-details-marker { display: none; }
    .merchant-switch-panel summary::after {
      content: "展开";
      position: absolute;
      right: 14px;
      top: 14px;
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }
    .merchant-switch-panel[open] summary::after { content: "收起"; }
    .merchant-switch-body {
      display: grid;
      gap: 10px;
      padding: 0 14px 14px;
    }
    .compact-merchants {
      gap: 8px;
      margin-top: 10px;
    }
    .compact-merchants .merchant {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 86px;
      gap: 8px;
      align-items: center;
      padding: 10px;
      border-radius: 14px;
    }
    .compact-merchants .merchant-head {
      margin: 0;
      min-width: 0;
    }
    .compact-merchants .merchant h3 {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .compact-merchants label {
      gap: 0;
      font-size: 0;
    }
    .compact-merchants select {
      min-height: 34px;
      padding: 6px 8px;
      border-radius: 10px;
    }
    .compact-merchants .hint {
      display: none;
    }
    .games {
      display: grid;
      gap: 10px;
    }
    .game-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: stretch;
    }
    .game-item {
      width: 100%;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 7px 10px;
      padding: 14px 14px 14px 16px;
      text-align: left;
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 18px;
      background: rgba(255,255,255,.05);
      color: #f4ede4;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
    }
    .game-order {
      display: grid;
      gap: 6px;
      align-content: center;
    }
    .game-order button {
      min-height: 34px;
      width: 38px;
      padding: 6px 0;
      border-radius: 12px;
      background: rgba(255,255,255,.08);
      color: #f4ede4;
      border-color: rgba(255,255,255,.12);
      box-shadow: none;
    }
    .game-order button:hover {
      background: rgba(255,255,255,.16);
    }
    .game-item.active {
      border-color: rgba(255,255,255,.14);
      background: linear-gradient(135deg, rgba(179,92,46,.22), rgba(255,255,255,.08));
      box-shadow: inset 4px 0 0 #f0c2a4, 0 12px 26px rgba(0,0,0,.16);
    }
    .game-title {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 700;
    }
    .game-sub {
      color: rgba(244, 237, 228, .62);
      font-size: 12px;
      grid-column: 1 / 2;
      overflow-wrap: anywhere;
    }
    .game-meta {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      grid-column: 1 / -1;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      border-radius: 999px;
      padding: 3px 9px;
      background: #eef2f6;
      color: var(--muted);
      font-size: 12px;
      border: 1px solid transparent;
    }
    .pill.ok { background: var(--ok-soft); color: var(--ok); }
    .pill.bad { background: var(--warn-soft); color: var(--warn); }
    .pill.info { background: var(--info-soft); color: var(--info); }
    .pill.soft { background: rgba(255,255,255,.14); color: inherit; border-color: rgba(255,255,255,.08); }
    .panel {
      background: var(--panel);
      border: 1px solid rgba(215, 204, 188, .95);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 18px;
      margin-bottom: 18px;
      position: relative;
      overflow: hidden;
      color: var(--text);
    }
    .panel::before {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(160deg, rgba(255,255,255,.55), transparent 28%);
      pointer-events: none;
    }
    .editor-shell {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 18px;
      align-content: start;
    }
    .editor-hero {
      position: sticky;
      top: 0;
      z-index: 1;
      display: grid;
      gap: 14px;
      margin: -26px -24px 0;
      padding: 26px 24px 18px;
      background:
        linear-gradient(180deg, rgba(235,231,223,.96) 0%, rgba(235,231,223,.92) 74%, rgba(235,231,223,0) 100%);
      backdrop-filter: blur(12px);
    }
    .workflow-card {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      padding: 14px;
      border: 1px solid rgba(215, 204, 188, .95);
      border-radius: 18px;
      background: rgba(255, 253, 249, .92);
      box-shadow: var(--shadow);
    }
    .workflow-step {
      padding: 10px 12px;
      border-radius: 14px;
      background: linear-gradient(135deg, rgba(244,239,230,.95), rgba(255,255,255,.85));
      border: 1px solid rgba(215, 204, 188, .85);
    }
    .workflow-step strong {
      display: block;
      margin-bottom: 4px;
      font-size: 13px;
    }
    .workflow-step span {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }
    .editor-columns {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 34%);
      gap: 18px;
      align-items: start;
    }
    .editor-main,
    .editor-side {
      display: grid;
      gap: 18px;
      align-content: start;
    }
    .editor-side {
      position: sticky;
      top: 150px;
    }
    .panel-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }
    .panel-title {
      margin: 0;
      font-size: 17px;
      font-weight: 760;
    }
    .panel-note {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .grid.single {
      grid-template-columns: 1fr;
    }
    .merchant-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
    }
    .merchant {
      border: 1px solid rgba(215, 204, 188, .95);
      border-radius: 18px;
      padding: 14px;
      background: linear-gradient(180deg, rgba(255,255,255,.92), rgba(244,239,230,.85));
    }
    .merchant h3 {
      margin: 0;
      font-size: 15px;
    }
    .merchant-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 10px;
    }
    .muted { color: var(--muted); }
    .status {
      min-height: 0;
      border: 1px solid transparent;
      border-radius: 10px;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.35;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      background: #f4efe7;
    }
    .status.ok {
      color: var(--ok);
      background: var(--ok-soft);
      border-color: #cfe9d8;
    }
    .status.warn {
      color: var(--warn);
      background: var(--warn-soft);
      border-color: #f0b4ae;
    }
    .status.info {
      color: var(--info);
      background: var(--info-soft);
      border-color: #bfd4ff;
    }
    .status.soft {
      color: var(--muted);
      background: #f8fafc;
      border-color: var(--line);
    }
    .empty {
      padding: 16px;
      border: 1px dashed var(--line-strong);
      border-radius: 16px;
      color: var(--muted);
      background: linear-gradient(135deg, #faf5ee, #f3eee7);
    }
    .hint {
      color: var(--muted);
      font-size: 12px;
      margin-top: 6px;
    }
    .text-right { text-align: right; }
    .text-center { text-align: center; }
    .match-name {
      font-weight: 700;
      margin-bottom: 4px;
    }
    .match-sub {
      color: var(--muted);
      font-size: 12px;
    }
    .compact-table th,
    .compact-table td {
      padding: 10px 10px;
    }
    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      background: transparent;
    }
    th, td {
      border-bottom: 1px solid rgba(215, 204, 188, .8);
      padding: 11px 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      background: #f5efe7;
      position: sticky;
      top: 0;
    }
    td { overflow-wrap: anywhere; }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); max-height: 38vh; }
      .grid { grid-template-columns: 1fr; }
      .overview { grid-template-columns: 1fr; }
      header { align-items: flex-start; }
      .editor-columns,
      .workflow-card { grid-template-columns: 1fr; }
      .editor-side { position: static; }
      .editor-hero { margin: -26px -24px 0; }
    }
  </style>
</head>
<body>
  <header>
    <div class="hero">
      <div>
        <h1>Switch 回收价游戏管理</h1>
        <p>维护游戏清单、商家商品 ID 和自动匹配结果，优先处理可采集、可发布的配置项。</p>
      </div>
      <div class="hero-actions">
        <button id="reloadBtn" title="刷新">刷新数据</button>
        <button id="newBtn" class="primary" title="新增游戏">新增游戏</button>
      </div>
    </div>
    <div class="overview">
      <div>
        <div class="overview-title">
          <span id="currentName" class="overview-name">请选择左侧游戏</span>
          <span id="currentEnabled" class="pill soft">未选择</span>
        </div>
        <div id="currentMeta" class="overview-sub">选择一款游戏后，这里会显示平台、Slug 和商家 ID 完整度。</div>
      </div>
      <div class="stat-row">
        <span id="summary" class="pill info"></span>
        <span id="coverageSummary" class="pill soft"></span>
        <span id="matchSummary" class="pill soft"></span>
      </div>
    </div>
  </header>
  <main>
    <aside>
      <div class="sidebar-top">
        <div class="panel">
          <div class="panel-title">游戏列表</div>
          <div class="panel-note">按名称、Slug 或平台搜索，优先处理 ID 缺失或待复核项目。</div>
          <div class="toolbar" style="margin:12px 0 0">
            <input id="filter" placeholder="搜索游戏">
          </div>
        </div>
        <details class="panel merchant-switch-panel">
          <summary>
          <div class="panel-title">回收商总开关</div>
          <div class="panel-note">接口异常时先在这里关闭对应回收商，采集和自动匹配会立刻跳过。</div>
          </summary>
          <div class="merchant-switch-body">
            <span id="merchantStatus" class="status soft">等待操作</span>
            <div id="merchantSettings" class="merchant-grid compact-merchants"></div>
          </div>
        </details>
      </div>
      <div id="games" class="games"></div>
    </aside>
    <section>
      <div class="editor-shell">
        <div class="editor-hero">
          <div class="workflow-card">
            <div class="workflow-step">
              <strong>1. 左侧找游戏</strong>
              <span>搜索或浏览列表，先锁定要处理的游戏。</span>
            </div>
            <div class="workflow-step">
              <strong>2. 右侧补数据</strong>
              <span>当前游戏的基础信息、搜索和商家 ID 固定在这一屏内完成。</span>
            </div>
            <div class="workflow-step">
              <strong>3. 直接保存</strong>
              <span>匹配结果和商家 ID 在同一区域，不需要来回滚动找位置。</span>
            </div>
          </div>
        </div>

        <div class="editor-columns">
          <div class="editor-main">
            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">基础信息</h2>
                  <div class="panel-note">先确认名称、平台和状态，确保当前选中的就是要维护的那一项。</div>
                </div>
                <span id="formStatus" class="status soft">等待编辑</span>
              </div>
              <div class="grid">
                <label>名称
                  <input id="name">
                </label>
                <label>平台
                  <select id="platform">
                    <option>Nintendo Switch</option>
                    <option>Nintendo Switch 2</option>
                  </select>
                </label>
                <label>唯一标识
                  <input id="slug">
                </label>
                <label>状态
                  <select id="enabled">
                    <option value="true">启用</option>
                    <option value="false">停用</option>
                  </select>
                </label>
              </div>
              <div class="toolbar" style="margin-top:12px;margin-bottom:0">
                <button id="saveBtn" class="primary">保存当前游戏</button>
                <button id="deleteBtn" class="danger">删除当前游戏</button>
              </div>
            </div>

            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">商家商品 ID</h2>
                  <div class="panel-note">这是当前游戏真正要维护的主区域。未填写的商家 ID 会在采集时标记为缺失。</div>
                </div>
              </div>
              <div id="merchants" class="merchant-grid"></div>
            </div>
          </div>

          <div class="editor-side">
            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">采集匹配</h2>
                  <div class="panel-note">搜索关键词和匹配结果固定放在右侧，查游戏后不用再往上翻找。</div>
                </div>
                <span id="searchStatus" class="status soft">还没有执行匹配</span>
              </div>
              <div class="grid single">
                <label>搜索关键词
                  <input id="searchKeyword">
                </label>
              </div>
              <div class="toolbar" style="margin-top:12px;margin-bottom:0">
                <button id="searchBtn" class="primary">自动匹配当前游戏</button>
                <button id="applySearchBtn">一键写入高置信候选</button>
              </div>
            </div>

            <div class="panel">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">匹配结果</h2>
                  <div class="panel-note">右侧直接看候选和建议动作，确认后立刻回填左边商家卡。</div>
                </div>
              </div>
              <div style="overflow:auto; max-height: 50vh;">
                <table class="compact-table">
                  <thead>
                    <tr>
                      <th>商家</th>
                      <th class="text-center">状态</th>
                      <th>建议动作</th>
                      <th>候选结果</th>
                      <th class="text-right">商品 ID</th>
                      <th class="text-right">置信度</th>
                    </tr>
                  </thead>
                  <tbody id="matches"></tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>
  <script>
    const state = { config: null, games: [], selected: null, matches: [] };
    const merchantNames = {};
    const $ = (id) => document.getElementById(id);

    function text(value) {
      return value == null ? "" : String(value);
    }

    function setStatus(id, tone, message) {
      const el = $(id);
      el.className = `status ${tone || "soft"}`;
      el.textContent = message;
    }

    function gameCoverage(game) {
      const merchants = Object.entries(state.config?.merchants || {})
        .filter(([, merchant]) => merchant.enabled !== false)
        .map(([key]) => key);
      const merchantIds = game?.merchant_ids || {};
      const filled = merchants.filter((key) => text(merchantIds[key]?.game_id).trim()).length;
      return { filled, total: merchants.length };
    }

    function selectedMatchSummary() {
      const total = state.matches.length;
      const matched = state.matches.filter((item) => item.status === "matched").length;
      return total ? `${matched}/${total} 项可直接应用` : "未执行匹配";
    }

    function matchDisplay(item) {
      if (item.search_status === "failed") return { tone: "bad", label: "请求失败", action: "检查网络或商家接口" };
      if (item.status === "matched") return { tone: "ok", label: "可直接应用", action: "可一键写入" };
      if ((item.raw_count || 0) === 0) return { tone: "soft", label: "无候选", action: "换关键词或人工查询" };
      return { tone: "info", label: "需要复核", action: "人工确认后再写入" };
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "content-type": "application/json" },
        ...options,
      });
      const data = await response.json();
      if (!response.ok || data.error) {
        throw new Error(data.error || response.statusText);
      }
      return data;
    }

    async function load() {
      const data = await api("/api/config");
      state.config = data;
      state.games = data.games || [];
      Object.keys(merchantNames).forEach((key) => delete merchantNames[key]);
      Object.entries(data.merchants || {}).forEach(([key, merchant]) => merchantNames[key] = merchant.name || key);
      if (!state.selected && state.games.length) state.selected = state.games[0].slug;
      if (state.selected && !state.games.find((game) => game.slug === state.selected)) {
        state.selected = state.games[0]?.slug || null;
      }
      render();
    }

    function selectedGame() {
      return state.games.find((game) => game.slug === state.selected) || null;
    }

    function render() {
      const filter = $("filter").value.trim().toLowerCase();
      const enabledCount = state.games.filter((game) => game.enabled !== false).length;
      $("summary").textContent = `${enabledCount}/${state.games.length} 款启用`;
      $("matchSummary").textContent = selectedMatchSummary();
      $("games").innerHTML = "";
      state.games
        .filter((game) => !filter || `${game.slug} ${game.name} ${game.platform}`.toLowerCase().includes(filter))
        .forEach((game) => {
          const index = state.games.findIndex((item) => item.slug === game.slug);
          const coverage = gameCoverage(game);
          const row = document.createElement("div");
          row.className = "game-row";
          const button = document.createElement("button");
          button.className = `game-item ${game.slug === state.selected ? "active" : ""}`;
          button.innerHTML = `
            <span class="game-title">${text(game.name)}</span>
            <span class="pill ${game.enabled === false ? "bad" : "ok"}">${game.enabled === false ? "停用" : "启用"}</span>
            <span class="game-sub">${text(game.slug)} · ${text(game.platform)}</span>
            <span class="game-meta">
              <span class="pill ${coverage.filled === coverage.total ? "ok" : coverage.filled ? "info" : "bad"}">ID ${coverage.filled}/${coverage.total}</span>
            </span>
          `;
          button.onclick = () => {
            state.selected = game.slug;
            state.matches = [];
            setStatus("searchStatus", "soft", "还没有执行匹配");
            render();
          };
          const controls = document.createElement("div");
          controls.className = "game-order";
          controls.innerHTML = `
            <button type="button" data-direction="up" title="Move up" ${index <= 0 ? "disabled" : ""}>↑</button>
            <button type="button" data-direction="down" title="Move down" ${index >= state.games.length - 1 ? "disabled" : ""}>↓</button>
          `;
          controls.querySelectorAll("button").forEach((orderButton) => {
            orderButton.onclick = (event) => {
              event.stopPropagation();
              moveGame(game.slug, orderButton.dataset.direction);
            };
          });
          row.appendChild(button);
          row.appendChild(controls);
          $("games").appendChild(row);
        });
      renderForm();
      renderMerchantSettings();
      renderMatches();
    }

    function renderMerchantSettings() {
      const container = $("merchantSettings");
      container.innerHTML = "";
      Object.entries(state.config?.merchants || {}).forEach(([key, merchant]) => {
        const enabled = merchant.enabled !== false;
        const box = document.createElement("div");
        box.className = "merchant";
        box.innerHTML = `
          <div class="merchant-head">
            <h3>${text(merchant.name || key)}</h3>
            <span class="pill ${enabled ? "ok" : "bad"}">${enabled ? "启用" : "停用"}</span>
          </div>
          <label>采集状态
            <select data-merchant-toggle="${key}">
              <option value="true" ${enabled ? "selected" : ""}>启用</option>
              <option value="false" ${enabled ? "" : "selected"}>停用</option>
            </select>
          </label>
          <div class="hint">${enabled ? "会参与采集、匹配和覆盖率统计。" : "已跳过采集，适合接口暂时不可用时关闭。"}</div>
        `;
        box.querySelector("select").onchange = (event) => updateMerchantEnabled(key, event.target.value === "true");
        container.appendChild(box);
      });
    }

    async function updateMerchantEnabled(key, enabled) {
      setStatus("merchantStatus", "info", "正在保存回收商状态...");
      try {
        await api(`/api/merchants/${encodeURIComponent(key)}`, {
          method: "POST",
          body: JSON.stringify({ enabled }),
        });
        setStatus("merchantStatus", "ok", "回收商状态已保存。");
        await load();
      } catch (error) {
        setStatus("merchantStatus", "warn", error.message);
      }
    }

    function renderForm() {
      const game = selectedGame();
      $("deleteBtn").disabled = !game;
      $("saveBtn").disabled = false;
      $("slug").value = text(game?.slug);
      $("name").value = text(game?.name);
      $("searchKeyword").value = text(game?.search_keyword);
      $("platform").value = text(game?.platform || "Nintendo Switch");
      $("enabled").value = String(game?.enabled !== false);
      $("currentName").textContent = text(game?.name || "请选择左侧游戏");
      $("currentEnabled").className = `pill ${game ? (game.enabled === false ? "bad" : "ok") : "soft"}`;
      $("currentEnabled").textContent = !game ? "未选择" : game.enabled === false ? "当前停用" : "当前启用";
      const coverage = gameCoverage(game);
      $("coverageSummary").textContent = game ? `商家 ID ${coverage.filled}/${coverage.total}` : "商家 ID 0/0";
      $("currentMeta").textContent = game
        ? `${text(game.platform)} · ${text(game.slug)} · 已配置 ${coverage.filled}/${coverage.total} 个商家商品 ID`
        : "选择一款游戏后，这里会显示平台、Slug 和商家 ID 完整度。";
      $("merchants").innerHTML = "";
      const merchantIds = game?.merchant_ids || {};
      if (!game) {
        $("merchants").innerHTML = `<div class="empty">请先从左侧选择一款游戏，或点击上方“新增游戏”开始创建。</div>`;
        return;
      }
      Object.entries(merchantNames).forEach(([key, name]) => {
        const ids = merchantIds[key] || {};
        const hasId = text(ids.game_id).trim();
        const box = document.createElement("div");
        box.className = "merchant";
        box.innerHTML = `
          <div class="merchant-head">
            <h3>${name}</h3>
            <span class="pill ${hasId ? "ok" : "bad"}">${hasId ? "已填写" : "待补充"}</span>
          </div>
          <label>商品 ID
            <input data-merchant="${key}" data-field="game_id" value="${text(ids.game_id)}">
          </label>
          <div class="hint">${hasId ? "已具备采集条件，可直接参与价格抓取。" : "建议先执行自动匹配，或手动补充后再采集。"}</div>
        `;
        $("merchants").appendChild(box);
      });
    }

    function collectForm() {
      const merchant_ids = {};
      $("merchants").querySelectorAll("input[data-merchant]").forEach((input) => {
        const key = input.dataset.merchant;
        const field = input.dataset.field;
        merchant_ids[key] ||= {};
        merchant_ids[key][field] = input.value.trim();
      });
      return {
        original_slug: state.selected,
        slug: $("slug").value.trim(),
        name: $("name").value.trim(),
        search_keyword: $("searchKeyword").value.trim(),
        platform: $("platform").value,
        enabled: $("enabled").value === "true",
        merchant_ids,
      };
    }

    async function saveGame() {
      setStatus("formStatus", "info", "正在保存当前游戏...");
      try {
        const payload = collectForm();
        const data = await api("/api/games", { method: "POST", body: JSON.stringify(payload) });
        state.selected = data.slug;
        setStatus("formStatus", "ok", "已保存，列表与商家 ID 已刷新。");
        await load();
      } catch (error) {
        setStatus("formStatus", "warn", error.message);
      }
    }

    async function deleteGame() {
      const game = selectedGame();
      if (!game) return;
      setStatus("formStatus", "warn", "正在删除当前游戏...");
      try {
        await api(`/api/games/${encodeURIComponent(game.slug)}`, { method: "DELETE" });
        state.selected = null;
        setStatus("formStatus", "ok", "已删除，已切回列表首项。");
        await load();
      } catch (error) {
        setStatus("formStatus", "warn", error.message);
      }
    }

    async function moveGame(slug, direction) {
      if (!slug || !direction) return;
      setStatus("formStatus", "info", direction === "up" ? "Moving game up..." : "Moving game down...");
      try {
        const data = await api("/api/games/reorder", {
          method: "POST",
          body: JSON.stringify({ slug, direction }),
        });
        state.selected = data.slug || slug;
        setStatus("formStatus", "ok", "Game order saved.");
        await load();
      } catch (error) {
        setStatus("formStatus", "warn", error.message);
      }
    }

    async function searchGame(apply = false) {
      const game = selectedGame();
      if (!game) return;
      setStatus("searchStatus", "info", apply ? "正在搜索并写入高置信候选..." : "正在搜索当前游戏的可用候选...");
      try {
        const data = await api(`/api/search?game=${encodeURIComponent(game.slug)}&apply=${apply ? "1" : "0"}`);
        state.matches = data.matches || [];
        const matched = state.matches.filter((item) => item.status === "matched").length;
        setStatus("searchStatus", apply ? "ok" : matched ? "ok" : "soft", apply ? `已写入 ${data.updated} 项高置信候选。` : `已完成搜索，找到 ${matched} 项可直接应用结果。`);
        if (apply) await load();
        renderMatches();
      } catch (error) {
        setStatus("searchStatus", "warn", error.message);
      }
    }

    function renderMatches() {
      $("matches").innerHTML = "";
      if (!state.matches.length) {
        $("matches").innerHTML = `<tr><td colspan="6"><div class="empty">还没有匹配结果。点击“自动匹配当前游戏”后，这里会展示候选和建议动作。</div></td></tr>`;
        $("matchSummary").textContent = "未执行匹配";
        return;
      }
      $("matchSummary").textContent = selectedMatchSummary();
      state.matches.forEach((item) => {
        const best = item.best || {};
        const display = matchDisplay(item);
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${merchantNames[item.merchant] || item.merchant}</td>
          <td class="text-center"><span class="pill ${display.tone}">${display.label}</span></td>
          <td>${display.action}</td>
          <td>
            <div class="match-name">${text(best.matched_name || item.search_error || "-")}</div>
            <div class="match-sub">${item.raw_count ? `候选 ${item.raw_count} 条` : "没有可用候选"}</div>
          </td>
          <td class="text-right">${text(best.game_id || "-")}</td>
          <td class="text-right">${text(best.confidence || "-")}</td>
        `;
        $("matches").appendChild(tr);
      });
    }

    $("reloadBtn").onclick = load;
    $("newBtn").onclick = () => {
      state.selected = null;
      state.matches = [];
      $("slug").value = "";
      $("name").value = "";
      $("searchKeyword").value = "";
      $("platform").value = "Nintendo Switch";
      $("enabled").value = "true";
      renderForm();
      setStatus("formStatus", "soft", "正在创建新游戏，填写后点击“保存当前游戏”。");
      setStatus("searchStatus", "soft", "新游戏保存后才可执行自动匹配。");
    };
    $("filter").oninput = render;
    $("saveBtn").onclick = saveGame;
    $("deleteBtn").onclick = deleteGame;
    $("searchBtn").onclick = () => searchGame(false);
    $("applySearchBtn").onclick = () => searchGame(true);
    load().catch((error) => setStatus("formStatus", "warn", error.message));
  </script>
</body>
</html>"""


class GameManagerHandler(BaseHTTPRequestHandler):
    config_path = "config.json"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server API
        return

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length") or "0")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                body = INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/config":
                config = load_config(self.config_path, resolve_env_vars=False)
                self.send_json(
                    {
                        "settings": config.get("settings", {}),
                        "merchants": config.get("merchants", {}),
                        "games": config.get("games", []),
                    }
                )
            elif parsed.path == "/api/search":
                query = parse_qs(parsed.query)
                game_slug = query.get("game", [""])[0]
                apply = query.get("apply", ["0"])[0] in ("1", "true", "yes")
                config = load_config(self.config_path, resolve_env_vars=False)
                matches = build_search_matches(config, game_slug=game_slug, top=5, page_size=10)
                updated = 0
                if apply:
                    updated = apply_search_matches(config, matches, threshold=0.75, overwrite=False)
                    save_config(config, self.config_path)
                self.send_json({"matches": matches, "updated": updated})
            else:
                self.send_json({"error": "not found"}, status=404)
        except Exception as exc:  # noqa: BLE001 - UI should return actionable errors.
            self.send_json({"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/games/reorder":
                payload = self.read_json()
                slug = str(payload.get("slug") or "").strip()
                direction = str(payload.get("direction") or "").strip()
                config = load_config(self.config_path, resolve_env_vars=False)
                games = config.get("games", [])
                index = next((i for i, game in enumerate(games) if game.get("slug") == slug), -1)
                if index < 0:
                    self.send_json({"error": f"Game not found: {slug}"}, status=404)
                    return
                if direction == "up":
                    target = index - 1
                elif direction == "down":
                    target = index + 1
                else:
                    self.send_json({"error": "direction must be up or down"}, status=400)
                    return
                if target < 0 or target >= len(games):
                    self.send_json({"slug": slug, "moved": False})
                    return
                games[index], games[target] = games[target], games[index]
                config["games"] = games
                save_config(config, self.config_path)
                self.send_json({"slug": slug, "moved": True})
                return
            if parsed.path.startswith("/api/merchants/"):
                merchant_key = parsed.path[len("/api/merchants/") :]
                payload = self.read_json()
                config = load_config(self.config_path, resolve_env_vars=False)
                merchant = config.get("merchants", {}).get(merchant_key)
                if not merchant:
                    self.send_json({"error": f"Merchant not found: {merchant_key}"}, status=404)
                    return
                merchant["enabled"] = bool(payload.get("enabled", True))
                save_config(config, self.config_path)
                self.send_json({"merchant": merchant_key, "enabled": merchant["enabled"]})
                return
            if parsed.path != "/api/games":
                self.send_json({"error": "not found"}, status=404)
                return
            payload = self.read_json()
            slug = str(payload.get("slug") or "").strip()
            name = str(payload.get("name") or "").strip()
            if not slug or not name:
                self.send_json({"error": "slug and name are required"}, status=400)
                return
            config = load_config(self.config_path, resolve_env_vars=False)
            original_slug = str(payload.get("original_slug") or "").strip()
            if original_slug:
                update_game(
                    config,
                    slug=original_slug,
                    new_slug=slug,
                    name=name,
                    platform=str(payload.get("platform") or "Nintendo Switch"),
                    search_keyword=str(payload.get("search_keyword") or ""),
                    enabled=bool(payload.get("enabled", True)),
                )
            else:
                add_game(config, slug=slug, name=name, platform=str(payload.get("platform") or "Nintendo Switch"))
                update_game(
                    config,
                    slug=slug,
                    search_keyword=str(payload.get("search_keyword") or ""),
                    enabled=bool(payload.get("enabled", True)),
                )
            for merchant, ids in (payload.get("merchant_ids") or {}).items():
                if not isinstance(ids, dict):
                    continue
                set_id(
                    config,
                    slug=slug,
                    merchant=str(merchant),
                    game_id=str(ids.get("game_id") or ""),
                    uuid=None if str(merchant) == "hangzhouxizi" else str(ids.get("uuid") or "") if "uuid" in ids else None,
                )
            save_config(config, self.config_path)
            self.send_json({"slug": slug})
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, status=500)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            prefix = "/api/games/"
            if not parsed.path.startswith(prefix):
                self.send_json({"error": "not found"}, status=404)
                return
            slug = parsed.path[len(prefix) :]
            config = load_config(self.config_path, resolve_env_vars=False)
            remove_game(config, slug=slug)
            save_config(config, self.config_path)
            self.send_json({"deleted": slug})
        except Exception as exc:  # noqa: BLE001
            self.send_json({"error": str(exc)}, status=500)


def run_ui(*, config_path: str = "config.json", host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    handler = type("ConfiguredGameManagerHandler", (GameManagerHandler,), {"config_path": config_path})
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}"
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    print(f"game manager ui: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("ui stopped")
    finally:
        server.server_close()
