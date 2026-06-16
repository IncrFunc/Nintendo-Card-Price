from pathlib import Path

from nsg_price.ui import INDEX_HTML, index_html, ui_asset_path


APP_JS = ui_asset_path("app.js").read_text(encoding="utf-8")
STYLES_CSS = ui_asset_path("styles.css").read_text(encoding="utf-8")
UI_PY = Path("nsg_price/ui.py").read_text(encoding="utf-8")


def test_index_html_is_loaded_from_resource_file():
    assert index_html() == INDEX_HTML


def test_merchant_switch_is_collapsed_sidebar_control():
    assert '<details class="panel merchant-switch-panel">' in INDEX_HTML
    assert '<summary>' in INDEX_HTML
    assert 'class="merchant-switch-body"' in INDEX_HTML
    assert "position: sticky;" not in STYLES_CSS.split(".sidebar-top", 1)[1].split(".sidebar-top .panel", 1)[0]
    assert ".merchant-switch-panel {" in STYLES_CSS
    assert "color: var(--text);" in STYLES_CSS


def test_search_results_allow_manual_candidate_apply():
    assert 'data-candidate-select="' in APP_JS
    assert 'data-apply-candidate="' in APP_JS
    assert '"/api/search/apply"' in APP_JS


def test_search_request_uses_current_keyword_input():
    assert 'const keyword = $("searchKeyword").value.trim();' in APP_JS
    assert 'params.set("keyword", keyword);' in APP_JS
    assert '`/api/search?${params.toString()}`' in APP_JS
    assert 'keyword = query.get("keyword", [""])[0].strip()' in UI_PY
    assert "search_keywords=[keyword] if keyword else None" in UI_PY


def test_editor_uses_three_column_workbench_layout():
    assert "Full reset redesign: calm operations console" in STYLES_CSS
    assert "<h1>Switch Price Ops</h1>" in INDEX_HTML
    assert "--primary: #057a55;" in STYLES_CSS
    assert "select option" in STYLES_CSS
    assert 'class="panel basic-panel"' in INDEX_HTML
    assert 'class="panel ids-panel"' in INDEX_HTML
    assert 'class="panel search-panel"' in INDEX_HTML
    assert 'class="panel match-panel"' in INDEX_HTML
    assert 'class="match-scroll"' in INDEX_HTML
    assert "<h2 class=\"panel-title\">游戏信息</h2>" in INDEX_HTML
    assert "左侧队列负责定位、排序和筛选" not in INDEX_HTML
    assert "基础信息、商家 ID 和匹配结果并排展示" not in INDEX_HTML
    assert "确认候选后直接写入当前游戏" not in INDEX_HTML
    assert ".editor-main {\n      display: contents;" in STYLES_CSS
    assert "grid-template-columns: minmax(300px, .72fr) minmax(560px, 1.28fr);" in STYLES_CSS
    assert "grid-template-rows: minmax(150px, .42fr) minmax(0, 1.58fr);" in STYLES_CSS


def test_game_list_supports_drag_reorder():
    assert "row.draggable = true;" in APP_JS
    assert 'class="drag-handle"' in APP_JS
    assert 'row.addEventListener("dragstart"' in APP_JS
    assert 'row.addEventListener("drop"' in APP_JS
    assert "target_slug" in APP_JS
    assert "placement" in APP_JS


def test_drag_reorder_auto_scrolls_game_list():
    assert "function autoScrollGames(clientY)" in APP_JS
    assert "list.scrollTop += delta;" in APP_JS
    assert "auto-scroll-up" in APP_JS
    assert "auto-scroll-down" in APP_JS


def test_partial_failed_search_with_candidates_is_not_shown_as_total_failure():
    assert 'label: "部分结果可应用"' in APP_JS
    assert 'label: "部分结果"' in APP_JS
    assert "function matchSubtext(item)" in APP_JS
    assert "部分请求失败" in APP_JS


def test_inner_html_templates_escape_dynamic_text():
    assert "function html(value)" in APP_JS
    assert '<span class="game-title">${html(game.name)}</span>' in APP_JS
    assert "<h3>${html(name)}</h3>" in APP_JS
    assert "${html(matchSubtext(item))}" in APP_JS


def test_index_html_references_split_assets():
    assert '<link rel="stylesheet" href="/assets/styles.css">' in INDEX_HTML
    assert '<script src="/assets/app.js"></script>' in INDEX_HTML
