from __future__ import annotations

import argparse
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from nsg_price.chart import generate_chart
from nsg_price.api_test import test_configured_apis
from nsg_price.automation import run_daily_automation, run_fetch_and_pack, run_xhs_publish
from nsg_price.collector import collect
from nsg_price.config import load_config, save_config
from nsg_price.config_tools import add_game, init_task_games, remove_game, set_game_enabled, set_id, update_ids_from_file
from nsg_price.doctor import build_doctor_report, format_doctor_report
from nsg_price.paths import api_test_results_path, doctor_report_path, publish_root, runtime_root
from nsg_price.publish import build_publish_pack
from nsg_price.report import generate_report
from nsg_price.search_ids import apply_search_matches, build_search_matches, write_search_match_outputs
from nsg_price.storage import export_csv, migrate_legacy_prices_to_shards
from nsg_price.utils import write_json
from nsg_price.xiaohongshu import launch_edge_for_xhs, publish_to_xiaohongshu


def summarize_records(records: list[dict]) -> tuple[int, int, int, int]:
    ok = sum(1 for record in records if record.get("status") == "ok")
    unavailable = sum(1 for record in records if record.get("status") == "unavailable")
    ready = sum(1 for record in records if record.get("status") == "ready")
    failed = len(records) - ok - unavailable - ready
    return ok, unavailable, ready, failed


def print_report_outputs(outputs: list[Path]) -> None:
    print("report generated:")
    for output in outputs:
        print(output)


def setup_logging() -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/collector.log", encoding="utf-8"),
        ],
    )


def cmd_fetch(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    records = collect(config, game_slug=args.game, dry_run=args.dry_run)
    ok, unavailable, ready, failed = summarize_records(records)
    print(f"fetch done: ok={ok}, unavailable={unavailable}, ready={ready}, failed/skipped={failed}, total={len(records)}")
    if args.csv:
        output = export_csv(config["settings"]["storage"]["prices_json"], config["settings"]["storage"]["csv_dir"])
        print(f"csv exported: {output}")
    if args.report and not args.dry_run:
        print_report_outputs(generate_report(config))


def cmd_schedule(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    if args.time:
        run_times = args.time
    else:
        settings = config.get("settings", {})
        run_times = settings.get("daily_fetch_times") or [settings.get("daily_fetch_time", "10:00")]
    print(f"scheduler started: daily at {', '.join(run_times)}")
    last_runs: set[tuple[str, str]] = set()
    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        run_key = (now.date().isoformat(), current_time)
        if current_time in run_times and run_key not in last_runs:
            records = collect(config)
            ok, unavailable, ready, failed = summarize_records(records)
            print(f"{now.isoformat(timespec='seconds')} fetch done: ok={ok}, unavailable={unavailable}, ready={ready}, failed/skipped={failed}")
            if args.report:
                print_report_outputs(generate_report(config, target_date=now.date().isoformat()))
            last_runs.add(run_key)
        time.sleep(30)


def cmd_chart(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    output = generate_chart(config, args.game)
    print(f"chart generated: {output}")


def cmd_add_game(args: argparse.Namespace) -> None:
    config = load_config(args.config, resolve_env_vars=False)
    add_game(config, slug=args.slug, name=args.name, platform=args.platform)
    save_config(config, args.config)
    print(f"game added: {args.slug}")


def cmd_init_task_games(args: argparse.Namespace) -> None:
    config = load_config(args.config, resolve_env_vars=False)
    count = init_task_games(config, replace=args.replace)
    save_config(config, args.config)
    print(f"task games initialized: changed={count}, replace={args.replace}")


def cmd_remove_game(args: argparse.Namespace) -> None:
    config = load_config(args.config, resolve_env_vars=False)
    remove_game(config, slug=args.slug)
    save_config(config, args.config)
    print(f"game removed: {args.slug}")


def cmd_set_game_enabled(args: argparse.Namespace) -> None:
    config = load_config(args.config, resolve_env_vars=False)
    set_game_enabled(config, slug=args.slug, enabled=args.enabled)
    save_config(config, args.config)
    print(f"game {'enabled' if args.enabled else 'disabled'}: {args.slug}")


def cmd_set_id(args: argparse.Namespace) -> None:
    config = load_config(args.config, resolve_env_vars=False)
    set_id(config, slug=args.game, merchant=args.merchant, game_id=args.game_id, uuid=args.uuid)
    save_config(config, args.config)
    print(f"id updated: {args.game}/{args.merchant}")


def cmd_export_csv(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    output = export_csv(config["settings"]["storage"]["prices_json"], config["settings"]["storage"]["csv_dir"])
    print(f"csv exported: {output}")


def cmd_migrate_prices(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    result = migrate_legacy_prices_to_shards(config["settings"]["storage"]["prices_json"], keep_backup=not args.no_backup)
    print(f"prices migrated: records={result['migrated']}, shard_dir={result['shard_dir']}, backup={result['backup']}")


def cmd_report(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    print_report_outputs(generate_report(config, target_date=args.date, session=args.session))


def cmd_publish_pack(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    output_dir, outputs = build_publish_pack(
        config,
        target_date=args.date,
        target_session=args.session,
        output_root=args.output_dir,
        regenerate_report=not args.no_regenerate_report,
    )
    print(f"publish pack generated: {output_dir}")
    for output in outputs:
        print(output)


def cmd_xhs_publish(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    result = publish_to_xiaohongshu(
        config=config,
        target_date=args.date,
        target_session=args.session,
        pack_dir=args.pack_dir,
        port=args.port,
        publish=args.publish,
        launch_edge=args.launch_edge,
        profile_dir=args.profile_dir,
        edge_path=args.edge_path,
    )
    print(f"xhs status: {result.status}")
    print(f"title: {result.title}")
    print(f"images: {result.image_count}")
    print(f"url: {result.url}")
    print(f"screenshot: {result.screenshot}")
    print(result.message)


def cmd_xhs_edge(args: argparse.Namespace) -> None:
    launch_edge_for_xhs(port=args.port, profile_dir=args.profile_dir, edge_path=args.edge_path)
    print(f"edge launched for Xiaohongshu automation: port={args.port}")


def cmd_auto_fetch(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    run_fetch_and_pack(config, target_date=args.date, session=args.session)


def cmd_auto_publish(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    run_xhs_publish(
        config,
        target_date=args.date,
        session=args.session,
        port=args.port,
        launch_edge=args.launch_edge,
        profile_dir=args.profile_dir,
        edge_path=args.edge_path,
    )


def cmd_auto(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(message: str) -> None:
        print(message, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    if args.ui:
        from nsg_price.ui import run_ui

        threading.Thread(
            target=run_ui,
            kwargs={
                "config_path": args.config,
                "host": args.ui_host,
                "port": args.ui_port,
                "open_browser": args.open_browser,
            },
            daemon=True,
        ).start()
        log(f"ui started: http://{args.ui_host}:{args.ui_port}")

    run_daily_automation(
        config,
        fetch_times=args.fetch_time,
        publish_times=args.publish_time,
        port=args.port,
        launch_edge=args.launch_edge,
        profile_dir=args.profile_dir,
        edge_path=args.edge_path,
        once=args.once,
        poll_seconds=args.poll_seconds,
        log=log,
    )


def cmd_doctor(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    report = build_doctor_report(config, target_date=args.date, session=args.session)
    if args.json:
        write_json(Path(args.output), report)
        print(f"doctor report written: {args.output}")
    else:
        print(format_doctor_report(report))


def cmd_update_ids(args: argparse.Namespace) -> None:
    config = load_config(args.config, resolve_env_vars=False)
    count = update_ids_from_file(config, merchant=args.merchant, file_path=args.file)
    save_config(config, args.config)
    print(f"ids updated: merchant={args.merchant}, count={count}")


def cmd_search_ids(args: argparse.Namespace) -> None:
    config = load_config(args.config, resolve_env_vars=False)
    matches = build_search_matches(
        config,
        game_slug=args.game,
        merchant=args.merchant,
        top=args.top,
        page_size=args.page_size,
        timeout=args.timeout,
    )
    updated = 0
    if args.apply:
        updated = apply_search_matches(config, matches, threshold=args.threshold, overwrite=args.overwrite)
        save_config(config, args.config)
    json_path, csv_path = write_search_match_outputs(matches, args.output_dir)
    matched = sum(1 for item in matches if item.get("status") == "matched")
    failed = sum(1 for item in matches if item.get("search_status") == "failed")
    print(f"search id matches generated: matched={matched}, failed_searches={failed}, total={len(matches)}, updated={updated}")
    print(f"json={json_path}")
    print(f"csv={csv_path}")


def cmd_test_api(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    results = test_configured_apis(config, game_slug=args.game)
    ok = sum(1 for item in results if item["status"] == "ok")
    unavailable = sum(1 for item in results if item["status"] == "unavailable")
    skipped = sum(1 for item in results if item["status"] == "skipped")
    failed = sum(1 for item in results if item["status"] == "failed")
    output = Path(args.output)
    write_json(output, results)
    print(f"api test done: ok={ok}, unavailable={unavailable}, skipped={skipped}, failed={failed}, output={output}")
    for item in results:
        label = f"{item['merchant']}/{item['game_slug']}"
        if item["status"] == "ok":
            print(f"OK      {label}: recycle_price={item.get('recycle_price')}")
        elif item["status"] == "unavailable":
            print(f"UNAVAIL {label}: {item.get('reason') or '不收别家'}")
        elif item["status"] == "skipped":
            print(f"SKIP    {label}: {item.get('reason')}")
        else:
            print(f"FAILED  {label}: {item.get('reason')}")


def cmd_ui(args: argparse.Namespace) -> None:
    from nsg_price.ui import run_ui

    run_ui(config_path=args.config, host=args.host, port=args.port, open_browser=args.open_browser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nintendo Switch cartridge recycle price collector")
    parser.add_argument("--config", default="config.json", help="config file path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="collect prices once")
    fetch.add_argument("--game", help="game slug to fetch")
    fetch.add_argument("--csv", action="store_true", help="export CSV after fetch")
    fetch.add_argument("--dry-run", action="store_true", help="validate config without remote requests")
    fetch.add_argument("--report", action=argparse.BooleanOptionalAction, default=True, help="generate report images after fetch")
    fetch.set_defaults(func=cmd_fetch)

    schedule = subparsers.add_parser("schedule", help="run daily scheduler")
    schedule.add_argument("--time", action="append", help="HH:MM local time; can be repeated")
    schedule.add_argument("--report", action=argparse.BooleanOptionalAction, default=True, help="generate report images after each scheduled fetch")
    schedule.set_defaults(func=cmd_schedule)

    chart = subparsers.add_parser("chart", help="generate HTML chart for a game")
    chart.add_argument("--game", required=True, help="game slug")
    chart.set_defaults(func=cmd_chart)

    add_game_parser = subparsers.add_parser("add-game", help="add a game to config")
    add_game_parser.add_argument("--slug", required=True)
    add_game_parser.add_argument("--name", required=True)
    add_game_parser.add_argument("--platform", default="Nintendo Switch")
    add_game_parser.set_defaults(func=cmd_add_game)

    init_games = subparsers.add_parser("init-task-games", help="initialize task.md game list into config")
    init_games.add_argument("--replace", action="store_true", help="replace current games with task list")
    init_games.set_defaults(func=cmd_init_task_games)

    remove_game_parser = subparsers.add_parser("remove-game", help="remove a game from config")
    remove_game_parser.add_argument("--slug", required=True)
    remove_game_parser.set_defaults(func=cmd_remove_game)

    disable_game_parser = subparsers.add_parser("disable-game", help="disable a game without deleting ids")
    disable_game_parser.add_argument("--slug", required=True)
    disable_game_parser.set_defaults(func=cmd_set_game_enabled, enabled=False)

    enable_game_parser = subparsers.add_parser("enable-game", help="enable a disabled game")
    enable_game_parser.add_argument("--slug", required=True)
    enable_game_parser.set_defaults(func=cmd_set_game_enabled, enabled=True)

    set_id_parser = subparsers.add_parser("set-id", help="set merchant id/uuid for a game")
    set_id_parser.add_argument("--game", required=True)
    set_id_parser.add_argument("--merchant", required=True)
    set_id_parser.add_argument("--game-id")
    set_id_parser.add_argument("--uuid")
    set_id_parser.set_defaults(func=cmd_set_id)

    export_parser = subparsers.add_parser("export-csv", help="export data/prices.json to CSV")
    export_parser.set_defaults(func=cmd_export_csv)

    migrate_prices = subparsers.add_parser("migrate-prices", help="migrate legacy prices.json into daily JSONL shards")
    migrate_prices.add_argument("--no-backup", action="store_true", help="do not keep a timestamped prices.json backup")
    migrate_prices.set_defaults(func=cmd_migrate_prices)

    report_parser = subparsers.add_parser("report", help="generate Xiaohongshu-style SVG report pages")
    report_parser.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    report_parser.add_argument("--session", choices=["am", "pm"], help="collection session to render")
    report_parser.set_defaults(func=cmd_report)

    publish_parser = subparsers.add_parser("publish-pack", help="build ordered Xiaohongshu image pack and caption")
    publish_parser.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    publish_parser.add_argument("--session", choices=["am", "pm"], help="collection session to package")
    publish_parser.add_argument("--output-dir", default=str(publish_root()))
    publish_parser.add_argument("--no-regenerate-report", action="store_true", help="use existing report files")
    publish_parser.set_defaults(func=cmd_publish_pack)

    xhs_publish = subparsers.add_parser("xhs-publish", help="upload a publish pack to Xiaohongshu creator")
    xhs_publish.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    xhs_publish.add_argument("--session", choices=["am", "pm"], help="collection session to upload")
    xhs_publish.add_argument("--pack-dir", help="explicit data/publish/<date> directory")
    xhs_publish.add_argument("--port", type=int, default=9223, help="Edge remote debugging port")
    xhs_publish.add_argument("--launch-edge", action="store_true", help="launch Edge with remote debugging before upload")
    xhs_publish.add_argument("--profile-dir", help="Edge user-data-dir to use with --launch-edge")
    xhs_publish.add_argument("--edge-path", help="path to msedge.exe")
    xhs_publish.add_argument("--publish", action="store_true", help="click the final publish button after filling content")
    xhs_publish.set_defaults(func=cmd_xhs_publish)

    xhs_edge = subparsers.add_parser("xhs-edge", help="launch controllable Edge for Xiaohongshu login")
    xhs_edge.add_argument("--port", type=int, default=9223, help="Edge remote debugging port")
    xhs_edge.add_argument("--profile-dir", help="Edge user-data-dir")
    xhs_edge.add_argument("--edge-path", help="path to msedge.exe")
    xhs_edge.set_defaults(func=cmd_xhs_edge)

    auto_fetch = subparsers.add_parser("auto-fetch", help="collect prices and build today's publish pack")
    auto_fetch.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    auto_fetch.add_argument("--session", choices=["am", "pm"], help="force publish-pack session")
    auto_fetch.set_defaults(func=cmd_auto_fetch)

    auto_publish = subparsers.add_parser("auto-publish", help="publish today's pack to Xiaohongshu")
    auto_publish.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    auto_publish.add_argument("--session", choices=["am", "pm"], help="collection session to publish")
    auto_publish.add_argument("--port", type=int, default=9223, help="Edge remote debugging port")
    auto_publish.add_argument("--launch-edge", action="store_true", help="launch Edge with remote debugging before publish")
    auto_publish.add_argument("--profile-dir", help="Edge user-data-dir to use with --launch-edge")
    auto_publish.add_argument("--edge-path", help="path to msedge.exe")
    auto_publish.set_defaults(func=cmd_auto_publish)

    auto = subparsers.add_parser("auto", help="run daily Python automation loop")
    auto.add_argument("--fetch-time", action="append", help="HH:MM fetch time; default 09:50 and 15:50")
    auto.add_argument(
        "--publish-time",
        action="append",
        help="HH:MM or HH:MM-HH:MM Xiaohongshu publish window; default 10:00-10:10 and 16:00-16:10",
    )
    auto.add_argument("--port", type=int, default=9223, help="Edge remote debugging port")
    auto.add_argument("--launch-edge", action="store_true", help="launch Edge with remote debugging when publishing")
    auto.add_argument("--profile-dir", help="Edge user-data-dir to use with --launch-edge")
    auto.add_argument("--edge-path", help="path to msedge.exe")
    auto.add_argument("--poll-seconds", type=int, default=20)
    auto.add_argument("--log-file", default="logs/automation.log")
    auto.add_argument("--ui", action="store_true", help="start the web UI in the same Python process")
    auto.add_argument("--ui-host", default="127.0.0.1")
    auto.add_argument("--ui-port", type=int, default=8765)
    auto.add_argument("--open-browser", action="store_true", help="open the UI browser when using --ui")
    auto.add_argument("--once", action="store_true", help="exit after the first due job runs")
    auto.set_defaults(func=cmd_auto)

    doctor_parser = subparsers.add_parser("doctor", help="check config coverage, tokens, schedule, and report outputs")
    doctor_parser.add_argument("--date", help="YYYY-MM-DD; defaults to today")
    doctor_parser.add_argument("--session", choices=["am", "pm"], help="collection session to check")
    doctor_parser.add_argument("--json", action="store_true", help="write JSON doctor report")
    doctor_parser.add_argument("--output", default=str(doctor_report_path()))
    doctor_parser.set_defaults(func=cmd_doctor)

    update_ids = subparsers.add_parser("update-ids", help="bulk update one merchant ids from CSV/JSON")
    update_ids.add_argument("--merchant", required=True)
    update_ids.add_argument("--file", required=True)
    update_ids.set_defaults(func=cmd_update_ids)

    search_ids = subparsers.add_parser("search-ids", help="search merchant APIs and match game ids directly")
    search_ids.add_argument("--game", help="game slug to search; defaults to all enabled games")
    search_ids.add_argument("--merchant", choices=["laolieren", "huoqiangshou", "hailuo", "hangzhouxizi", "baibiandui"], help="merchant to search")
    search_ids.add_argument("--output-dir", default=str(runtime_root()))
    search_ids.add_argument("--top", type=int, default=5)
    search_ids.add_argument("--page-size", type=int, default=10)
    search_ids.add_argument("--timeout", type=int, help="request timeout seconds")
    search_ids.add_argument("--apply", action="store_true", help="write high-confidence search matches into config/games file")
    search_ids.add_argument("--threshold", type=float, default=0.75)
    search_ids.add_argument("--overwrite", action="store_true", help="replace existing configured ids")
    search_ids.set_defaults(func=cmd_search_ids)

    test_api = subparsers.add_parser("test-api", help="test configured real APIs with local ids/tokens")
    test_api.add_argument("--game", help="game slug to test")
    test_api.add_argument("--output", default=str(api_test_results_path()))
    test_api.set_defaults(func=cmd_test_api)

    ui = subparsers.add_parser("ui", help="start local web UI for game management")
    ui.add_argument("--host", default="127.0.0.1")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--open-browser", action="store_true", help="open browser after server starts")
    ui.set_defaults(func=cmd_ui)

    return parser


def main() -> None:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
