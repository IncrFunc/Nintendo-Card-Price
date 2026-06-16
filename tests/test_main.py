from main import build_parser, summarize_records


def test_summarize_records_counts_unavailable_separately():
    records = [
        {"status": "ok"},
        {"status": "unavailable"},
        {"status": "ready"},
        {"status": "skipped"},
        {"status": "error"},
    ]
    assert summarize_records(records) == (1, 1, 1, 2)


def test_search_ids_cli_accepts_mogushijian():
    parser = build_parser()

    args = parser.parse_args(["search-ids", "--merchant", "mogushijian"])

    assert args.merchant == "mogushijian"
