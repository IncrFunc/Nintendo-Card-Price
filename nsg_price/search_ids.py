from __future__ import annotations

import csv
import difflib
import os
import re
from pathlib import Path
from typing import Any

import requests

from .config import enabled_games, find_game
from .config_tools import set_id
from .constants import DEFAULT_XIZI_UUID
from .utils import write_json

SEARCH_MERCHANTS = ("laolieren", "huoqiangshou", "hailuo", "hangzhouxizi", "baibiandui", "mogushijian")
MINI_HEADERS = {
    "cb-lang": "zh-CN",
    "appid": "wx7f7b845076caaf81",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541939) XWEB/19841",
    "xweb_xhr": "1",
    "form-type": "routine",
    "content-type": "application/json",
    "accept": "*/*",
    "sec-fetch-site": "cross-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://servicewechat.com/wx7f7b845076caaf81/73/page-frame.html",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "zh-CN,zh;q=0.9",
    "priority": "u=1, i",
}

MATCH_RULES: dict[str, list[list[str]]] = {
    "zelda-breath-of-the-wild": [["旷野之息", "荒野之息"]],
    "zelda-tears-of-the-kingdom": [["王国之泪"]],
    "super-mario-party-jamboree": [["空前盛会"], ["马里奥", "马力欧"]],
    "zelda-breath-of-the-wild-bundle": [["旷野之息", "荒野之息", "野炊"], ["同捆", "dlc", "+dlc", "扩充票", "扩充版", "全dlc"]],
    "zelda-echoes-of-wisdom": [["智慧的再现", "智慧再现"]],
    "fitness-boxing-3": [["有氧拳击3", "健身拳击3"]],
    "super-mario-odyssey": [["奥德赛"]],
    "kirby-and-the-forgotten-land": [["探索发现"], ["星之卡比", "卡比"]],
    "pokemon-legends-z-a": [["z-a", "za"], ["宝可梦", "口袋妖怪"]],
    "splatoon-3": [["喷射战士3", "斯普拉遁", "斯普拉顿"]],
    "super-mario-bros-wonder": [["惊奇"], ["马里奥", "马力欧"]],
    "mario-kart-8-deluxe": [["赛车8", "马车8"]],
    "luigis-mansion-3": [["鬼屋3", "洋馆3"]],
    "it-takes-two": [["双人成行"]],
    "dave-the-diver": [["潜水员戴夫"]],
    "tomodachi-life-living-the-dream": [["朋友聚会", "朋友收集", "梦想生活"]],
    "super-mario-party-jamboree-tv-ns2": [["空前盛会"], ["tv"]],
    "zelda-tears-of-the-kingdom-ns2": [["王国之泪"]],
    "zelda-breath-of-the-wild-ns2": [["旷野之息", "荒野之息"]],
    "donkey-kong-bananza": [["蕉力全开"], ["大金刚", "咚奇刚"]],
    "mario-kart-world": [["赛车世界", "马车世界", "马车9"]],
    "cyberpunk-2077-ns2": [["赛博朋克2077", "赛博朋克 2077"]],
    "kirby-star-world-ns2": [["星耀世界"], ["星之卡比", "卡比"]],
    "pokemon-pokopia": [["pokopia"]],
    "hyrule-warriors-age-of-imprisonment": [["封印战记"], ["塞尔达无双"]],
    "kirby-air-riders": [["驭天飞行", "御天飞行"]],
}
REJECT_RULES: dict[str, list[str]] = {
    "zelda-breath-of-the-wild": ["扩充", "dlc", "同捆"],
    "super-mario-party-jamboree": ["tv"],
    "kirby-and-the-forgotten-land": ["星耀世界"],
    "pokemon-legends-z-a": ["朱紫", "扩充票"],
    "splatoon-3": ["扩充票", "dlc"],
    "mario-kart-8-deluxe": ["扩充版", "dlc"],
}
SYNONYMS = {
    "马力欧": "马里奥",
    "荒野之息": "旷野之息",
    "鬼屋": "洋馆",
    "斯普拉遁": "斯普拉顿",
    "塞尔达传说2": "塞尔达传说 王国之泪",
    "咚奇刚": "大金刚",
    "驭天飞行": "御天飞行",
    "朋友聚会": "朋友收集",
}
NOISE = ("ns", "ns1", "ns2", "switch", "nintendo", "游戏", "卡带", "中文", "港版", "日版", "标准版", "特别版", "传说", "超级", "兄弟")


def baibiandui_headers(t_token: str | None = None) -> dict[str, str]:
    headers = dict(MINI_HEADERS)
    headers["appid"] = "wx81ceaf48bed4bb56"
    headers["referer"] = "https://servicewechat.com/wx81ceaf48bed4bb56/4/page-frame.html"
    token = t_token or os.getenv("BAIBIANDUI_T") or ""
    if token:
        headers["t"] = token
    return headers


def hailuo_headers(authorization: str | None = None) -> dict[str, str]:
    headers = dict(MINI_HEADERS)
    headers["appid"] = "wx7f7b845076caaf81"
    headers["referer"] = os.getenv("HAILUO_REFERER") or "https://servicewechat.com/wx7f7b845076caaf81/76/page-frame.html"
    token = authorization or os.getenv("HAILUO_AUTHORIZATION") or os.getenv("HAILUO_BEARER_TOKEN") or ""
    if token:
        headers["authori-zation"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    return headers


def hangzhouxizi_headers(recyclexcx: str | None = None) -> dict[str, str]:
    token = recyclexcx or os.getenv("XIZI_RECYCLEXCX") or ""
    headers = {
        "user-agent": MINI_HEADERS["user-agent"],
        "xweb_xhr": "1",
        "content-type": "application/json",
        "accept": "*/*",
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": os.getenv("XIZI_REFERER") or "https://servicewechat.com/wxdf78c51363de71d4/4/page-frame.html",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9",
        "priority": "u=1, i",
    }
    if token:
        headers["recyclexcx"] = token
    return headers


def mogushijian_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "user-agent": MINI_HEADERS["user-agent"],
        "xweb_xhr": "1",
        "content-type": "application/json",
        "alianame": os.getenv("MOGUSHIJIAN_ALIANAME") or "alia2",
        "accept": "*/*",
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": os.getenv("MOGUSHIJIAN_REFERER") or "https://servicewechat.com/wx95e68e4fbf89d3f7/3/page-frame.html",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "zh-CN,zh;q=0.9",
    }
    resolved_token = token or os.getenv("MOGUSHIJIAN_TOKEN") or ""
    if resolved_token:
        headers["Token"] = resolved_token
    return headers


def huoqiangshou_headers() -> dict[str, str]:
    return {
        "terminal": "WECHAT",
        "user-agent": MINI_HEADERS["user-agent"],
        "xweb_xhr": "1",
        "content-type": "application/x-www-form-urlencoded",
        "accept": "*/*",
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": os.getenv("HUOQIANGSHOU_REFERER") or "https://servicewechat.com/wx0f883cb942dd9691/630/page-frame.html",
        "accept-language": "zh-CN,zh;q=0.9",
    }


def parse_laolieren_list_item(item: dict[str, Any]) -> dict[str, Any] | None:
    item_id = item.get("id")
    title = item.get("title")
    if not item_id or not title:
        return None
    return {"merchant": "laolieren", "item_id": str(item_id), "name": str(title), "platform": item.get("platform")}


def parse_huoqiangshou_list_item(item: dict[str, Any]) -> dict[str, Any] | None:
    item_id = item.get("id") or item.get("productId")
    name = item.get("productName") or item.get("name") or item.get("title")
    if not item_id or not name:
        return None
    return {"merchant": "huoqiangshou", "item_id": str(item_id), "name": str(name), "platform": item.get("brandName")}


def parse_baibiandui_list_item(item: dict[str, Any]) -> dict[str, Any] | None:
    item_id = item.get("id")
    name = item.get("title") or item.get("name")
    if not item_id or not name:
        return None
    return {"merchant": "baibiandui", "item_id": str(item_id), "name": str(name), "platform": item.get("brandName") or item.get("platform")}


def parse_mogushijian_list_item(item: dict[str, Any]) -> dict[str, Any] | None:
    item_id = item.get("cardsId")
    name = item.get("name")
    if not item_id or not name:
        return None
    return {
        "merchant": "mogushijian",
        "item_id": str(item_id),
        "name": str(name),
        "platform": "Nintendo Switch 2" if str(item.get("generationType")) == "2" else "Nintendo Switch",
        "sell_price": item.get("price"),
        "en_name": item.get("enName"),
    }


def normalize(text: str) -> str:
    value = text.lower()
    for old, new in SYNONYMS.items():
        value = value.replace(old.lower(), new.lower())
    value = re.sub(r"[\s\-_/·:：,，。()（）\[\]【】+]+", "", value)
    for word in NOISE:
        value = value.replace(word, "")
    return value


def target_is_ns2(game: dict[str, Any]) -> bool:
    return "2" in str(game.get("platform", "")) or str(game.get("slug", "")).endswith("-ns2")


def name_is_ns2(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in ("ns2", "switch2", "switch 2", "2代"))


def name_is_other_platform(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in ("ps4", "ps5", "xbox", "xsx", "xss", "steam", "pc ", "pc版", "playstation"))


def platform_allowed(game: dict[str, Any], candidate_name: str) -> bool:
    if name_is_other_platform(candidate_name):
        return False
    if target_is_ns2(game):
        return name_is_ns2(candidate_name)
    return not name_is_ns2(candidate_name)


def rule_passes(slug: str, candidate_name: str) -> bool:
    if slug not in MATCH_RULES:
        return False
    normalized_name = normalize(candidate_name)
    for reject in REJECT_RULES.get(slug, []):
        if normalize(reject) in normalized_name:
            return False
    for group in MATCH_RULES.get(slug, []):
        if not any(normalize(term) in normalized_name for term in group):
            return False
    return True


def numbers_in(text: str) -> list[str]:
    return re.findall(r"\d+", normalize(text))


def fallback_rule_passes(game: dict[str, Any], candidate_name: str) -> bool:
    query = normalize(str(game.get("name", "")))
    name = normalize(candidate_name)
    if not query or query not in name:
        return False
    query_numbers = numbers_in(query)
    candidate_numbers = numbers_in(name)
    if not query_numbers:
        return True
    return any(
        candidate_numbers[index : index + len(query_numbers)] == query_numbers
        for index in range(len(candidate_numbers) - len(query_numbers) + 1)
    )


def candidate_auto_match_passes(game: dict[str, Any], candidate_name: str) -> bool:
    if not platform_allowed(game, candidate_name):
        return False
    slug = str(game.get("slug", ""))
    if slug in MATCH_RULES:
        return rule_passes(slug, candidate_name)
    return fallback_rule_passes(game, candidate_name)


def confidence(game: dict[str, Any], candidate_name: str) -> float:
    query = normalize(str(game.get("name", "")))
    name = normalize(candidate_name)
    ratio = difflib.SequenceMatcher(None, query, name).ratio()
    overlap = len(set(query) & set(name)) / max(len(set(query) | set(name)), 1)
    containment = 0.25 if query and (query in name or name in query) else 0.0
    platform_bonus = 0.12 if (target_is_ns2(game) == name_is_ns2(candidate_name)) else 0.0
    rule_bonus = 0.25 if rule_passes(str(game.get("slug", "")), candidate_name) else 0.0
    return round(min(1.0, max(ratio, overlap) + containment + platform_bonus + rule_bonus), 3)


def candidates_for_game(game: dict[str, Any], merchant: str, rows: list[dict[str, str]], top: int = 5) -> list[dict[str, Any]]:
    scored = []
    slug = str(game.get("slug", ""))
    for row in rows:
        name = row.get("game_name", "")
        if not name or not row.get("game_id"):
            continue
        allowed = platform_allowed(game, name)
        passes = candidate_auto_match_passes(game, name)
        scored.append(
            {
                "merchant": merchant,
                "game_slug": slug,
                "target_name": game.get("name"),
                "matched_name": name,
                "game_id": row.get("game_id"),
                "uuid": row.get("uuid", ""),
                "confidence": confidence(game, name),
                "rule_passed": passes,
                "platform_passed": allowed,
            }
        )
    return sorted(scored, key=lambda item: (item["rule_passed"], item["confidence"]), reverse=True)[:top]


def search_keywords_for_game(game: dict[str, Any]) -> list[str]:
    values: list[str] = []
    explicit = game.get("search_keywords") or game.get("search_keyword")
    if isinstance(explicit, list):
        values.extend(str(item) for item in explicit if str(item).strip())
    elif explicit:
        values.append(str(explicit))
    name = str(game.get("name") or "").strip()
    if name:
        values.append(name)
    for group in MATCH_RULES.get(str(game.get("slug") or ""), []):
        values.extend(str(item) for item in group if str(item).strip())
    seen: set[str] = set()
    keywords = []
    for value in values:
        keyword = value.strip()
        if keyword and keyword.lower() not in seen:
            keywords.append(keyword)
            seen.add(keyword.lower())
    return keywords


def rows_at(payload: Any, paths: list[tuple[str, ...]]) -> list[dict[str, Any]]:
    for path in paths:
        current = payload
        for key in path:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                current = None
                break
        if isinstance(current, list):
            return [item for item in current if isinstance(item, dict)]
    return []


def parse_hailuo_search_item(item: dict[str, Any]) -> dict[str, Any] | None:
    item_id = item.get("id") or item.get("store_id") or item.get("productId")
    name = item.get("store_name") or item.get("title") or item.get("name")
    if not item_id or not name:
        return None
    return {
        "merchant": "hailuo",
        "item_id": str(item_id),
        "name": str(name),
        "platform": item.get("cate_name") or item.get("platform"),
        "brand_name": item.get("brand_name"),
        "product_type": item.get("type"),
        "status": item.get("status"),
        "sell_price": item.get("price"),
        "keyword": item.get("keyword"),
        "alias": item.get("store_info"),
    }


def parse_hangzhouxizi_search_item(item: dict[str, Any], uuid: str | None = None) -> dict[str, Any] | None:
    item_id = item.get("id") or item.get("commodityId")
    name = item.get("name") or item.get("commodityName") or item.get("title")
    if not item_id or not name:
        return None
    return {
        "merchant": "hangzhouxizi",
        "item_id": str(item_id),
        "name": str(name),
        "platform": item.get("platform") or item.get("brandName"),
        "brand_name": item.get("brandName"),
        "product_type": item.get("type"),
        "status": item.get("status"),
        "sell_price": item.get("price"),
        "uuid": str(item.get("uuid") or uuid or ""),
        "keyword": item.get("keyword"),
        "alias": item.get("alias"),
    }


def normalize_search_records(merchant: str, payload: dict[str, Any], uuid: str | None = None) -> list[dict[str, Any]]:
    if merchant == "laolieren":
        rows = rows_at(payload, [("rows",), ("data", "rows"), ("data", "list"), ("data",)])
        parser = parse_laolieren_list_item
    elif merchant == "huoqiangshou":
        rows = rows_at(payload, [("data", "rows"), ("rows",), ("data", "list"), ("data",)])
        parser = parse_huoqiangshou_list_item
    elif merchant == "baibiandui":
        rows = rows_at(payload, [("data", "list"), ("data", "rows"), ("rows",), ("data",)])
        parser = parse_baibiandui_list_item
    elif merchant == "mogushijian":
        rows = rows_at(payload, [("list",), ("data", "list"), ("data", "rows"), ("rows",), ("data",)])
        parser = parse_mogushijian_list_item
    elif merchant == "hailuo":
        rows = rows_at(payload, [("data",), ("data", "list"), ("data", "rows"), ("rows",)])
        parser = parse_hailuo_search_item
    elif merchant == "hangzhouxizi":
        rows = rows_at(payload, [("data", "list"), ("data", "rows"), ("rows",), ("data",)])

        def parser(item: dict[str, Any]) -> dict[str, Any] | None:
            return parse_hangzhouxizi_search_item(item, uuid=uuid)

    else:
        raise ValueError(f"unsupported merchant: {merchant}")

    records = []
    for row in rows:
        record = parser(row)
        if record:
            records.append(record)
    return records


def request_search_payload(
    session: requests.Session,
    merchant: str,
    keyword: str,
    *,
    page: int = 1,
    page_size: int = 10,
    timeout: int = 10,
    uuid: str | None = None,
) -> dict[str, Any]:
    if merchant == "laolieren":
        response = session.post(
            "https://api.laolieren.com/v2/game/home",
            headers={"content-type": "application/json"},
            json={
                "auth": "",
                "page": page,
                "app": "weixin",
                "filter": {"platform": "", "keyword": keyword, "listorder": "", "favorite": "", "genres": "", "preset": ""},
            },
            timeout=timeout,
            verify=False,
        )
    elif merchant == "huoqiangshou":
        body = {
            "pageNumber": str(page),
            "pageNum": str(page),
            "pageSize": str(page_size),
            "brandId": "",
            "productType": "CARD",
            "productName": keyword,
            "monthSale": "",
            "stockNum": "",
            "supportChinese": "",
            "screenPrice": "",
            "timeSort": "",
            "startPrice": "0",
            "endPrice": "999",
            "linkStatus": "",
            "gameType": "",
        }
        response = session.post(
            "https://api.huoqiangshou.cn/seller/category/getProductInfoPage",
            headers=huoqiangshou_headers(),
            data=body,
            timeout=timeout,
            verify=False,
        )
    elif merchant == "baibiandui":
        response = session.post(
            "https://api.aemacross.com/goodsInfo/list",
            headers=baibiandui_headers(),
            json={"page": page, "limit": page_size, "title": keyword, "parentId": ""},
            timeout=timeout,
            verify=False,
        )
    elif merchant == "hailuo":
        response = session.get(
            "https://hailuo.dwzjd.com/api/products",
            headers=hailuo_headers(),
            params={
                "cid": "0",
                "sid": "0",
                "keyword": keyword,
                "priceOrder": "",
                "salesOrder": "",
                "news": "0",
                "best": "0",
                "store_label_id": "",
                "page": str(page),
                "limit": str(page_size),
                "coupon_category_id": "",
                "productId": "",
            },
            timeout=timeout,
            verify=False,
        )
    elif merchant == "hangzhouxizi":
        response = session.post(
            "https://api.recycle.steamlease.cn/commodity/getCommodityListPage",
            headers=hangzhouxizi_headers(),
            json={"uuid": uuid or DEFAULT_XIZI_UUID, "classify_id": "", "name": keyword, "pageNum": page, "pageSize": page_size},
            timeout=timeout,
            verify=False,
        )
    elif merchant == "mogushijian":
        response = session.post(
            "https://api.mogushijian.com/alia/used/search",
            headers=mogushijian_headers(),
            json={"name": keyword, "page": page, "type": 2},
            timeout=timeout,
            verify=False,
        )
    else:
        raise ValueError(f"unsupported merchant: {merchant}")

    response.raise_for_status()
    return response.json()


def search_merchant(
    merchant: str,
    keyword: str,
    *,
    page: int = 1,
    page_size: int = 10,
    timeout: int = 10,
    uuid: str | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    active_session = session or requests.Session()
    payload = request_search_payload(
        active_session,
        merchant,
        keyword,
        page=page,
        page_size=page_size,
        timeout=timeout,
        uuid=uuid,
    )
    return normalize_search_records(merchant, payload, uuid=uuid)


def search_all_merchants(
    keyword: str | list[str],
    *,
    merchants: list[str] | None = None,
    page_size: int = 10,
    timeout: int = 10,
    uuid: str | None = None,
) -> dict[str, dict[str, Any]]:
    session = requests.Session()
    results: dict[str, dict[str, Any]] = {}
    keywords = [keyword] if isinstance(keyword, str) else keyword
    for merchant in merchants or list(SEARCH_MERCHANTS):
        records: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        errors: list[str] = []
        try:
            for item in keywords:
                found = search_merchant(merchant, item, page_size=page_size, timeout=timeout, uuid=uuid, session=session)
                for record in found:
                    record_id = str(record.get("item_id") or "")
                    if record_id and record_id not in seen_ids:
                        records.append(record)
                        seen_ids.add(record_id)
            results[merchant] = {"status": "ok", "records": records}
        except Exception as exc:  # noqa: BLE001 - one merchant search should not hide the others.
            errors.append(str(exc))
            results[merchant] = {"status": "failed", "error": "; ".join(errors), "records": records}
    return results


def build_search_matches(
    config: dict[str, Any],
    *,
    game_slug: str | None = None,
    merchant: str | None = None,
    top: int = 5,
    page_size: int = 10,
    timeout: int | None = None,
) -> list[dict[str, Any]]:
    request_settings = config.get("settings", {}).get("request", {})
    effective_timeout = int(timeout or request_settings.get("timeout_seconds", 10))
    merchants = [merchant] if merchant else [key for key in SEARCH_MERCHANTS if key in config.get("merchants", {})]
    matches: list[dict[str, Any]] = []
    for game in enabled_games(config, game_slug):
        keywords = search_keywords_for_game(game)
        xizi_uuid = (
            config.get("settings", {}).get("default_xizi_uuid")
            or game.get("merchant_ids", {}).get("hangzhouxizi", {}).get("uuid")
            or DEFAULT_XIZI_UUID
        )
        search_results = search_all_merchants(keywords, merchants=merchants, page_size=page_size, timeout=effective_timeout, uuid=str(xizi_uuid))
        for merchant_key in merchants:
            result = search_results.get(merchant_key, {"status": "failed", "records": [], "error": "not searched"})
            rows = [{"game_name": row.get("name", ""), "game_id": row.get("item_id", ""), "uuid": row.get("uuid", "")} for row in result["records"]]
            candidates = candidates_for_game(game, merchant_key, rows, top=top)
            best = candidates[0] if candidates else None
            matches.append(
                {
                    "game_slug": game.get("slug"),
                    "game_name": game.get("name"),
                    "platform": game.get("platform"),
                    "keyword": ", ".join(keywords),
                    "merchant": merchant_key,
                    "search_status": result.get("status"),
                    "search_error": result.get("error"),
                    "status": "matched" if best and best["rule_passed"] else "needs_review",
                    "best": best,
                    "candidates": candidates,
                    "raw_count": len(result["records"]),
                }
            )
    return matches


def apply_search_matches(config: dict[str, Any], matches: list[dict[str, Any]], threshold: float = 0.75, overwrite: bool = False) -> int:
    updated = 0
    for item in matches:
        best = item.get("best") or {}
        if item.get("status") != "matched" or float(best.get("confidence") or 0) < threshold:
            continue
        game = find_game(config, str(item.get("game_slug")))
        if not game:
            continue
        merchant = str(item.get("merchant"))
        ids = game.setdefault("merchant_ids", {}).setdefault(merchant, {})
        if ids.get("game_id") and not overwrite:
            continue
        uuid = None if merchant == "hangzhouxizi" else str(best.get("uuid") or "") or None
        set_id(config, slug=str(item["game_slug"]), merchant=merchant, game_id=str(best["game_id"]), uuid=uuid)
        updated += 1
    return updated


def write_search_match_outputs(matches: list[dict[str, Any]], output_dir: str | Path = "data/runtime") -> tuple[Path, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "search_id_matches.json"
    csv_path = output_path / "search_id_matches.csv"
    write_json(json_path, matches)
    fields = [
        "game_slug",
        "game_name",
        "platform",
        "keyword",
        "merchant",
        "search_status",
        "status",
        "matched_name",
        "game_id",
        "uuid",
        "confidence",
        "raw_count",
        "search_error",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for item in matches:
            best = item.get("best") or {}
            writer.writerow(
                {
                    "game_slug": item.get("game_slug"),
                    "game_name": item.get("game_name"),
                    "platform": item.get("platform"),
                    "keyword": item.get("keyword"),
                    "merchant": item.get("merchant"),
                    "search_status": item.get("search_status"),
                    "status": item.get("status"),
                    "matched_name": best.get("matched_name", ""),
                    "game_id": best.get("game_id", ""),
                    "uuid": best.get("uuid", ""),
                    "confidence": best.get("confidence", ""),
                    "raw_count": item.get("raw_count", 0),
                    "search_error": item.get("search_error", ""),
                }
            )
    return json_path, csv_path
