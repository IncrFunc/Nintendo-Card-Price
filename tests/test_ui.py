from nsg_price.ui import INDEX_HTML


def test_merchant_switch_is_collapsed_sidebar_control():
    assert '<details class="panel merchant-switch-panel">' in INDEX_HTML
    assert '<summary>' in INDEX_HTML
    assert 'class="merchant-switch-body"' in INDEX_HTML
    assert "position: sticky;" not in INDEX_HTML.split(".sidebar-top", 1)[1].split(".sidebar-top .panel", 1)[0]
    assert ".merchant-switch-panel {" in INDEX_HTML
    assert "color: var(--text);" in INDEX_HTML
