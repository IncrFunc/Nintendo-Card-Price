from nsg_price.ui import INDEX_HTML


def test_merchant_switch_is_collapsed_sidebar_control():
    assert '<details class="panel merchant-switch-panel">' in INDEX_HTML
    assert '<summary>' in INDEX_HTML
    assert 'class="merchant-switch-body"' in INDEX_HTML
    assert "position: sticky;" not in INDEX_HTML.split(".sidebar-top", 1)[1].split(".sidebar-top .panel", 1)[0]
    assert ".merchant-switch-panel {" in INDEX_HTML
    assert "color: var(--text);" in INDEX_HTML


def test_search_results_allow_manual_candidate_apply():
    assert 'data-candidate-select="' in INDEX_HTML
    assert 'data-apply-candidate="' in INDEX_HTML
    assert '"/api/search/apply"' in INDEX_HTML


def test_editor_uses_three_column_workbench_layout():
    assert 'class="panel basic-panel"' in INDEX_HTML
    assert 'class="panel ids-panel"' in INDEX_HTML
    assert 'class="panel search-panel"' in INDEX_HTML
    assert 'class="panel match-panel"' in INDEX_HTML
    assert 'class="match-scroll"' in INDEX_HTML
    assert ".editor-main {\n      display: contents;" in INDEX_HTML
    assert "grid-template-columns: minmax(220px, .72fr) minmax(300px, 1fr) minmax(300px, .95fr);" in INDEX_HTML
