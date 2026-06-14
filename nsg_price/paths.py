from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def _settings(config: dict[str, Any] | None) -> dict[str, Any]:
    return (config or {}).get("settings", {})


def _storage(config: dict[str, Any] | None) -> dict[str, Any]:
    return _settings(config).get("storage", {})


def _path_from_config(value: str | None, default: str) -> Path:
    return Path(value or default)


def reports_root(config: dict[str, Any] | None = None) -> Path:
    return _path_from_config(_storage(config).get("reports_dir"), "data/reports")


def report_dir(target_date: str, config: dict[str, Any] | None = None) -> Path:
    return reports_root(config) / target_date


def publish_root(config: dict[str, Any] | None = None) -> Path:
    return _path_from_config(_storage(config).get("publish_dir"), "data/publish")


def publish_dir(target_date: str, config: dict[str, Any] | None = None) -> Path:
    return publish_root(config) / target_date

def runtime_root(config: dict[str, Any] | None = None) -> Path:
    return _path_from_config(_storage(config).get("runtime_dir"), "data/runtime")


def doctor_report_path(config: dict[str, Any] | None = None) -> Path:
    return runtime_root(config) / "doctor_report.json"


def api_test_results_path(config: dict[str, Any] | None = None) -> Path:
    return runtime_root(config) / "api_test_results.json"


def today_date() -> str:
    return datetime.now().date().isoformat()
