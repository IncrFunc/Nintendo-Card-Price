from main import summarize_records


def test_summarize_records_counts_unavailable_separately():
    records = [
        {"status": "ok"},
        {"status": "unavailable"},
        {"status": "ready"},
        {"status": "skipped"},
        {"status": "error"},
    ]
    assert summarize_records(records) == (1, 1, 1, 2)
