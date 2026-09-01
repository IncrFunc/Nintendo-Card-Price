import pytest

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

    args = parser.parse_args(["auto", "--device", "emulator-5554", "--adb-path", "adb.exe"])

    assert args.device == "emulator-5554"
    assert args.adb_path == "adb.exe"


def test_auto_publish_cli_is_adb_only():
    parser = build_parser()

    args = parser.parse_args(["auto-publish"])

    assert args.func.__name__ == "cmd_auto_publish"


def test_xhs_adb_push_images_cli_is_available():
    parser = build_parser()

    args = parser.parse_args(["xhs-adb-push-images", "--date", "2026-06-27", "--device", "emulator-5554"])

    assert args.func.__name__ == "cmd_xhs_adb_push_images"
    assert args.date == "2026-06-27"
    assert args.device == "emulator-5554"


def test_xhs_adb_replace_latest_images_cli_is_available():
    parser = build_parser()

    args = parser.parse_args(
        [
            "xhs-adb-replace-latest-images",
            "--date",
            "2026-06-27",
            "--device",
            "emulator-5554",
            "--old-image-count",
            "3",
            "--submit",
        ]
    )

    assert args.func.__name__ == "cmd_xhs_adb_replace_latest_images"
    assert args.date == "2026-06-27"
    assert args.device == "emulator-5554"
    assert args.old_image_count == 3
    assert args.submit is True


@pytest.mark.parametrize(
    "argv",
    [
        ["xhs-edge"],
        ["xhs-publish"],
        ["report", "--session", "am"],
        ["publish-pack", "--session", "pm"],
        ["xhs-adb-publish", "--session", "am"],
        ["auto-fetch", "--session", "am"],
        ["auto-publish", "--session", "pm"],
        ["auto-publish", "--driver", "browser"],
        ["auto", "--publish-driver", "browser"],
        ["auto", "--launch-edge"],
        ["auto", "--edge-path", "msedge.exe"],
    ],
)
def test_cli_rejects_edge_browser_and_session_options(argv):
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(argv)
