from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .collector import collect
from .paths import today_date
from .publish import build_publish_pack
from .xiaohongshu import publish_to_xiaohongshu


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


def session_for_schedule_time(value: str) -> str:
    return "am" if value < "12:00" else "pm"


def run_fetch_and_pack(config: dict, *, target_date: str | None = None, session: str | None = None, log: Logger = print) -> AutomationEvent:
    date = target_date or today_date()
    log(f"[{datetime.now().isoformat(timespec='seconds')}] fetch started for {date} {session or ''}".rstrip())
    records = collect(config)
    ok = sum(1 for record in records if record.get("status") == "ok")
    unavailable = sum(1 for record in records if record.get("status") == "unavailable")
    ready = sum(1 for record in records if record.get("status") == "ready")
    failed = len(records) - ok - unavailable - ready
    output_dir, outputs = build_publish_pack(config, target_date=date, target_session=session, regenerate_report=True)
    message = (
        f"fetch done: ok={ok}, unavailable={unavailable}, ready={ready}, "
        f"failed/skipped={failed}, total={len(records)}, publish_pack={output_dir}, files={len(outputs)}"
    )
    log(f"[{datetime.now().isoformat(timespec='seconds')}] {message}")
    return AutomationEvent(kind="fetch", date=date, message=message)


def run_xhs_publish(
    config: dict,
    *,
    target_date: str | None = None,
    session: str | None = None,
    port: int = 9223,
    launch_edge: bool = False,
    profile_dir: str | Path | None = None,
    edge_path: str | Path | None = None,
    log: Logger = print,
) -> AutomationEvent:
    date = target_date or today_date()
    log(f"[{datetime.now().isoformat(timespec='seconds')}] xhs publish started for {date} {session or ''}".rstrip())
    result = publish_to_xiaohongshu(
        config=config,
        target_date=date,
        target_session=session,
        port=port,
        publish=True,
        launch_edge=launch_edge,
        profile_dir=profile_dir,
        edge_path=edge_path,
    )
    message = f"xhs status={result.status}, images={result.image_count}, url={result.url}, screenshot={result.screenshot}"
    log(f"[{datetime.now().isoformat(timespec='seconds')}] {message}")
    return AutomationEvent(kind="xhs-publish", date=date, message=message)


def run_daily_automation(
    config: dict,
    *,
    fetch_times: list[str] | None = None,
    publish_times: list[str] | None = None,
    port: int = 9223,
    launch_edge: bool = False,
    profile_dir: str | Path | None = None,
    edge_path: str | Path | None = None,
    once: bool = False,
    poll_seconds: int = 20,
    log: Logger = print,
) -> None:
    normalized_fetch_times = _normalize_times(fetch_times, ["09:55", "15:55"])
    normalized_publish_times = _normalize_times(publish_times, ["10:00", "16:00"])
    log(
        "automation started: "
        f"fetch at {', '.join(normalized_fetch_times)}; "
        f"xhs publish at {', '.join(normalized_publish_times)}"
    )
    ran: set[tuple[str, str, str]] = set()
    while True:
        now = datetime.now()
        date = now.date().isoformat()
        current_time = now.strftime("%H:%M")
        if current_time in normalized_fetch_times and ("fetch", date, current_time) not in ran:
            session = session_for_schedule_time(current_time)
            try:
                run_fetch_and_pack(config, target_date=date, session=session, log=log)
            except Exception as exc:
                log(f"[{datetime.now().isoformat(timespec='seconds')}] fetch failed: {exc!r}")
            ran.add(("fetch", date, current_time))
            if once:
                return
        if current_time in normalized_publish_times and ("xhs-publish", date, current_time) not in ran:
            session = session_for_schedule_time(current_time)
            try:
                run_xhs_publish(
                    config,
                    target_date=date,
                    session=session,
                    port=port,
                    launch_edge=launch_edge,
                    profile_dir=profile_dir,
                    edge_path=edge_path,
                    log=log,
                )
            except Exception as exc:
                log(f"[{datetime.now().isoformat(timespec='seconds')}] xhs publish failed: {exc!r}")
            ran.add(("xhs-publish", date, current_time))
            if once:
                return
        time.sleep(poll_seconds)
