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


def test_auto_cli_accepts_adb_publish_options():
    parser = build_parser()

    args = parser.parse_args(["auto", "--publish-driver", "adb", "--device", "2527b8b", "--adb-path", "adb.exe"])

    assert args.publish_driver == "adb"
    assert args.device == "2527b8b"
    assert args.adb_path == "adb.exe"


def test_auto_publish_cli_accepts_adb_driver():
    parser = build_parser()

    args = parser.parse_args(["auto-publish", "--driver", "adb", "--session", "am"])

    assert args.driver == "adb"
    assert args.session == "am"
