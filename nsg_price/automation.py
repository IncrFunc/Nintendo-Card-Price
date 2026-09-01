from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, time as datetime_time
import random
from pathlib import Path
from typing import Callable

from .adb_xiaohongshu import publish_pack_via_adb
from .collector import collect
from .paths import publish_root, runtime_root, today_date
from .publish import build_publish_pack


@dataclass(frozen=True)
class AutomationEvent:
    kind: str
    date: str
    message: str


Logger = Callable[[str], None]


def _normalize_times(values: list[str] | None, default: list[str]) -> list[str]:
    times = values or default
    for value in times:
        datetime.strptime(value, "%H:%M")
    return times


def _normalize_publish_windows(values: list[str] | None, default: list[str]) -> list[str]:
    windows = values or default
    for value in windows:
        parse_publish_window(value)
    return windows


def parse_publish_window(value: str) -> tuple[datetime_time, datetime_time]:
    if "-" not in value:
        parsed = datetime.strptime(value, "%H:%M").time()
        return parsed, parsed
    start_text, end_text = [item.strip() for item in value.split("-", 1)]
    start = datetime.strptime(start_text, "%H:%M").time()
    end = datetime.strptime(end_text, "%H:%M").time()
    if (end.hour, end.minute) < (start.hour, start.minute):
        raise ValueError(f"publish window must not cross midnight: {value}")
    return start, end


def pick_time_in_window(value: str, *, rng: random.Random | None = None) -> str:
    start, end = parse_publish_window(value)
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    minute = (rng or random).randint(start_minutes, end_minutes)
    return f"{minute // 60:02d}:{minute % 60:02d}"


def planned_publish_times_for_date(
    windows: list[str],
    *,
    date: str,
    rng: random.Random | None = None,
) -> dict[str, str]:
    return {window: pick_time_in_window(window, rng=rng) for window in windows}


def scheduled_time_is_due(now: datetime, value: str) -> bool:
    scheduled = datetime.combine(now.date(), datetime.strptime(value, "%H:%M").time())
    return now >= scheduled


def run_fetch_and_pack(config: dict, *, target_date: str | None = None, log: Logger = print) -> AutomationEvent:
    date = target_date or today_date()
    log(f"[{datetime.now().isoformat(timespec='seconds')}] fetch started for {date}")
    records = collect(config)
    ok = sum(1 for record in records if record.get("status") == "ok")
    unavailable = sum(1 for record in records if record.get("status") == "unavailable")
    ready = sum(1 for record in records if record.get("status") == "ready")
    failed = len(records) - ok - unavailable - ready
    output_dir, outputs = build_publish_pack(config, target_date=date, regenerate_report=True)
    message = (
        f"fetch done: ok={ok}, unavailable={unavailable}, ready={ready}, "
        f"failed/skipped={failed}, total={len(records)}, publish_pack={output_dir}, files={len(outputs)}"
    )
    log(f"[{datetime.now().isoformat(timespec='seconds')}] {message}")
    return AutomationEvent(kind="fetch", date=date, message=message)


def run_xhs_adb_publish(
    config: dict,
    *,
    target_date: str | None = None,
    adb_path: str | Path | None = None,
    serial: str | None = None,
    output_dir: str | Path | None = None,
    log: Logger = print,
) -> AutomationEvent:
    date = target_date or today_date()
    pack_dir = publish_root(config) / date
    log(f"[{datetime.now().isoformat(timespec='seconds')}] xhs adb publish started for {date}")
    result = publish_pack_via_adb(
        pack_dir,
        adb_path=adb_path,
        serial=serial,
        publish=True,
        output_dir=output_dir or runtime_root(config) / "adb-xhs",
    )
    message = (
        f"xhs adb status={result.status}, device={result.serial}, images={result.image_count}, "
        f"remote_dir={result.remote_dir}, remote_deleted={result.remote_deleted}, screenshot={result.screenshot}"
    )
    log(f"[{datetime.now().isoformat(timespec='seconds')}] {message}")
    return AutomationEvent(kind="xhs-adb-publish", date=date, message=message)


def run_daily_automation(
    config: dict,
    *,
    config_loader: Callable[[], dict] | None = None,
    fetch_times: list[str] | None = None,
    publish_times: list[str] | None = None,
    adb_path: str | Path | None = None,
    adb_serial: str | None = None,
    adb_output_dir: str | Path | None = None,
    once: bool = False,
    poll_seconds: int = 20,
    log: Logger = print,
) -> None:
    settings = config.get("settings", {})
    default_fetch_times = settings.get("daily_fetch_times") or ["11:50"]
    default_publish_windows = settings.get("daily_publish_windows") or ["12:00-12:10"]
    normalized_fetch_times = _normalize_times(fetch_times, default_fetch_times)
    normalized_publish_windows = _normalize_publish_windows(publish_times, default_publish_windows)
    planned_date = ""
    planned_publish_times: dict[str, str] = {}
    log(
        "automation started: "
        f"fetch at {', '.join(normalized_fetch_times)}; "
        f"xhs publish windows {', '.join(normalized_publish_windows)}; "
        "publish driver adb"
    )
    ran: set[tuple[str, str, str]] = set()
    jobs: dict[tuple[str, str, str], Future[bool]] = {}
    outcomes: dict[tuple[str, str, str], bool] = {}

    def current_config() -> dict:
        return config_loader() if config_loader else config

    def fetch_job(date: str) -> bool:
        try:
            run_fetch_and_pack(current_config(), target_date=date, log=log)
            return True
        except Exception as exc:
            log(f"[{datetime.now().isoformat(timespec='seconds')}] fetch failed: {exc!r}")
            return False

    def publish_job(date: str) -> bool:
        try:
            run_xhs_adb_publish(
                current_config(),
                target_date=date,
                adb_path=adb_path,
                serial=adb_serial,
                output_dir=adb_output_dir,
                log=log,
            )
            return True
        except Exception as exc:
            log(f"[{datetime.now().isoformat(timespec='seconds')}] xhs adb publish failed: {exc!r}")
            return False

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="nsg-automation") as executor:
        while True:
            now = datetime.now()
            date = now.date().isoformat()
            if date != planned_date:
                planned_date = date
                planned_publish_times = planned_publish_times_for_date(normalized_publish_windows, date=date)
                log(
                    f"[{datetime.now().isoformat(timespec='seconds')}] "
                    f"today's xhs publish times: {', '.join(planned_publish_times.values())}"
                )

            for key, future in jobs.items():
                if future.done() and key not in outcomes:
                    outcomes[key] = future.result()

            submitted: list[Future[bool]] = []
            for fetch_time in normalized_fetch_times:
                key = ("fetch", date, fetch_time)
                if not scheduled_time_is_due(now, fetch_time) or key in ran:
                    continue
                ran.add(key)
                jobs[key] = executor.submit(fetch_job, date)
                submitted.append(jobs[key])

            due_fetch_keys = [
                ("fetch", date, fetch_time)
                for fetch_time in normalized_fetch_times
                if scheduled_time_is_due(now, fetch_time)
            ]
            fetch_is_running = any(key in jobs and not jobs[key].done() for key in due_fetch_keys)
            fetch_succeeded = all(outcomes.get(key) is True for key in due_fetch_keys)

            if not fetch_is_running and fetch_succeeded:
                for window, publish_time in planned_publish_times.items():
                    key = ("xhs-adb-publish", date, window)
                    if not scheduled_time_is_due(now, publish_time) or key in ran:
                        continue
                    ran.add(key)
                    jobs[key] = executor.submit(publish_job, date)
                    submitted.append(jobs[key])

            if once and submitted:
                for future in submitted:
                    future.result()
                return

            time.sleep(poll_seconds)
