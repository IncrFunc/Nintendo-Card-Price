from __future__ import annotations

import time
from typing import Any

import requests


CATALOG_URL = "https://api.zhualegezhua.cn/alia/used/recycle/cardsList"


def catalog_headers() -> dict[str, str]:
    return {
        "content-type": "application/json",
        "alianame": "alia2",
        "accept": "*/*",
    }


def fetch_catalog(
    session: requests.Session,
    *,
    timeout: int = 10,
    retries: int = 2,
    backoff: float = 1,
    verify: bool = True,
    max_pages: int = 200,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    seen_pages: set[int] = set()

    while page <= max_pages:
        if page in seen_pages:
            raise RuntimeError(f"mogushijian catalog repeated page: {page}")
        seen_pages.add(page)

        last_error: Exception | None = None
        payload: dict[str, Any] | None = None
        for attempt in range(retries + 1):
            try:
                response = session.post(
                    CATALOG_URL,
                    headers=catalog_headers(),
                    json={"page": page},
                    timeout=timeout,
                    verify=verify,
                )
                response.raise_for_status()
                payload = response.json()
                break
            except Exception as exc:  # noqa: BLE001 - retry one catalog page as a unit.
                last_error = exc
                if attempt < retries:
                    time.sleep(backoff * (attempt + 1))

        if payload is None:
            raise RuntimeError(str(last_error))

        page_rows = payload.get("list")
        if not isinstance(page_rows, list):
            raise RuntimeError("mogushijian catalog missing list")
        rows.extend(item for item in page_rows if isinstance(item, dict))

        if not payload.get("hasMore"):
            return rows
        next_page = payload.get("next")
        page = int(next_page) if next_page is not None else page + 1

    raise RuntimeError(f"mogushijian catalog exceeded {max_pages} pages")
