from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .utils import as_money, get_path

@dataclass
class ParsedPrice:
    game_name: str | None
    item_id: str | None
    sku_id: str | None
    sell_price: float | None
    recycle_price: float | None
    currency: str = "CNY"
    status: str = "ok"
    parser_note: str | None = None


class ParserError(ValueError):
    pass


NAME_PATHS = [
    "row.name",
    "row.title",
    "row.game_name",
    "data.name",
    "data.title",
    "data.productName",
    "data.goodsName",
    "data.commodityName",
    "data.storeInfo.store_name",
    "data.info.name",
    "data.goods.name",
    "name",
]

ITEM_ID_PATHS = [
    "row.id",
    "data.id",
    "data.productId",
    "data.goodsId",
    "data.commodityId",
    "data.storeInfo.id",
    "data.info.id",
    "id",
]

SKU_ID_PATHS = [
    "data.skuId",
    "data.sku_id",
    "data.sku.id",
    "data.info.skuId",
]

SELL_PRICE_PATHS = [
    "row.price",
    "data.sellPrice",
    "data.salePrice",
    "data.price",
    "data.goodsPrice",
    "data.goods.price",
    "data.replacementSecondHandPrice",
    "data.marketPrice",
    "data.info.price",
    "data.goods.price",
    "data.goods.replacementSecondHandPrice",
]

RECYCLE_PRICE_PATHS = [
    "data.receivePrice",
    "data.recyclePrice",
    "data.recoveryPrice",
    "data.buybackPrice",
    "data.apprizePrice",
    "data.valuationPrice",
    "data.recycleSecondHandPrice",
    "data.recycleBareCardPrice",
    "data.recycleGuidePrice",
    "data.price",
    "data.goods.receivePrice",
    "data.goods.recyclePrice",
    "data.goods.recycleSecondHandPrice",
    "data.goods.recycleBareCardPrice",
    "data.info.receivePrice",
    "data.info.recyclePrice",
]

DEDUCT_PATHS = [
    "data.minusPrice",
    "data.deductPrice",
    "data.offsetPrice",
    "data.recycleDeduct",
    "data.buyDeduct",
]


def first_value(data: Any, paths: list[str]) -> Any:
    for path in paths:
        value = get_path(data, path)
        if value not in (None, ""):
            return value
    return None


def find_money_by_key(data: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(data, dict):
        for key, value in data.items():
            lowered = key.lower()
            if any(fragment in lowered for fragment in keys):
                money = as_money(value)
                if money is not None:
                    return money
            found = find_money_by_key(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_money_by_key(item, keys)
            if found is not None:
                return found
    return None


def parse_generic(data: dict[str, Any], *, note: str | None = None) -> ParsedPrice:
    name = first_value(data, NAME_PATHS)
    item_id = first_value(data, ITEM_ID_PATHS)
    sku_id = first_value(data, SKU_ID_PATHS)
    sell_price = as_money(first_value(data, SELL_PRICE_PATHS))
    recycle_price = as_money(first_value(data, RECYCLE_PRICE_PATHS))

    if recycle_price is None:
        recycle_price = find_money_by_key(
            data,
            (
                "receiveprice",
                "recycleprice",
                "recoveryprice",
                "buybackprice",
                "apprizeprice",
                "valuationprice",
            ),
        )

    if recycle_price is None and sell_price is not None:
        deduct = as_money(first_value(data, DEDUCT_PATHS))
        if deduct is None:
            deduct = find_money_by_key(data, ("deduct", "minus", "offset"))
        if deduct is not None:
            recycle_price = sell_price - deduct
            note = note or "recycle_price=sell_price-deduct"

    if recycle_price is None:
        raise ParserError("No recycle price field found in response")

    return ParsedPrice(
        game_name=str(name) if name is not None else None,
        item_id=str(item_id) if item_id is not None else None,
        sku_id=str(sku_id) if sku_id is not None else None,
        sell_price=sell_price,
        recycle_price=recycle_price,
        parser_note=note,
    )


def parse_laolieren(data: dict[str, Any]) -> ParsedPrice:
    row = data.get("row") or {}
    name = first_value(data, NAME_PATHS)
    item_id = first_value(data, ITEM_ID_PATHS)
    if str(row.get("is_outside")) == "0":
        return ParsedPrice(
            game_name=str(name) if name else None,
            item_id=str(item_id) if item_id else None,
            sku_id=None,
            sell_price=as_money(row.get("price")),
            recycle_price=None,
            status="unavailable",
            parser_note="row.is_outside=0",
        )
    sell_price = as_money(row.get("price"))
    outside_diff = as_money(row.get("outside_diff"))
    if sell_price is None or outside_diff is None:
        raise ParserError("老猎人缺少 row.price 或 row.outside_diff")
    return ParsedPrice(
        game_name=str(name) if name else None,
        item_id=str(item_id) if item_id else None,
        sku_id=None,
        sell_price=sell_price,
        recycle_price=sell_price + outside_diff,
        parser_note="recycle_price=row.price+row.outside_diff",
    )


def huoqiangshou_other_shop_reduce(apprize: dict[str, Any]) -> float | None:
    questions = get_path(apprize, "data.listProductQuestion")
    if not isinstance(questions, list):
        return None
    for question in questions:
        answers = question.get("answers") if isinstance(question, dict) else None
        if not isinstance(answers, list):
            continue
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            text = f"{answer.get('name', '')}{answer.get('valueType', '')}".lower()
            if any(marker in text for marker in ("别店", "别家", "其他", "other_shop")):
                reduce_price = as_money(answer.get("reducePrice"))
                if reduce_price is not None:
                    return reduce_price
    return None


def parse_huoqiangshou(data: dict[str, Any]) -> ParsedPrice:
    detail = data.get("detail") if isinstance(data.get("detail"), dict) else data
    apprize = data.get("apprize") if isinstance(data.get("apprize"), dict) else {}
    detail_data = detail.get("data") or {}
    receive_price = as_money(detail_data.get("receivePrice"))
    if receive_price is None:
        raise ParserError("火枪手缺少 detail.data.receivePrice")

    reduce_price = huoqiangshou_other_shop_reduce(apprize)
    if reduce_price is None:
        return ParsedPrice(
            game_name=str(first_value(detail, NAME_PATHS)) if first_value(detail, NAME_PATHS) is not None else None,
            item_id=str(first_value(detail, ITEM_ID_PATHS)) if first_value(detail, ITEM_ID_PATHS) is not None else None,
            sku_id=None,
            sell_price=as_money(detail_data.get("retailPrice")),
            recycle_price=None,
            status="unavailable",
            parser_note="huoqiangshou no other-shop recycle option",
        )

    name = first_value(detail, NAME_PATHS)
    item_id = first_value(detail, ITEM_ID_PATHS)
    sku_id = first_value(detail, SKU_ID_PATHS)
    return ParsedPrice(
        game_name=str(name) if name is not None else None,
        item_id=str(item_id) if item_id is not None else None,
        sku_id=str(sku_id) if sku_id is not None else None,
        sell_price=None,
        recycle_price=receive_price - reduce_price,
        parser_note="recycle_price=detail.data.receivePrice-apprize.data.listProductQuestion[0].answers[1].reducePrice",
    )


def parse_hailuo(data: dict[str, Any]) -> ParsedPrice:
    if data.get("status") == 400533:
        return ParsedPrice(
            game_name=None,
            item_id=None,
            sku_id=None,
            sell_price=None,
            recycle_price=None,
            status="skipped",
            parser_note=f"hailuo product unavailable: {data.get('msg') or 'product missing'}",
        )
    store = get_path(data, "data.storeInfo") or {}
    name = first_value(data, NAME_PATHS)
    item_id = first_value(data, ITEM_ID_PATHS)
    if str(store.get("out_recycle")) == "0":
        return ParsedPrice(
            game_name=str(name) if name else None,
            item_id=str(item_id) if item_id else None,
            sku_id=None,
            sell_price=as_money(store.get("price")),
            recycle_price=None,
            status="unavailable",
            parser_note="data.storeInfo.out_recycle=0",
        )
    sell_price = as_money(store.get("price"))
    out_diff = as_money(store.get("out_diff"))
    if sell_price is None or out_diff is None:
        raise ParserError("海螺缺少 data.storeInfo.price 或 data.storeInfo.out_diff")
    return ParsedPrice(
        game_name=str(name) if name else None,
        item_id=str(item_id) if item_id else None,
        sku_id=None,
        sell_price=sell_price,
        recycle_price=sell_price - out_diff,
        parser_note="recycle_price=data.storeInfo.price-data.storeInfo.out_diff",
    )


def parse_hangzhouxizi(data: dict[str, Any]) -> ParsedPrice:
    if isinstance(data.get("detail"), dict) or isinstance(data.get("guige"), dict):
        detail = data.get("detail") if isinstance(data.get("detail"), dict) else {}
        guige = data.get("guige") if isinstance(data.get("guige"), dict) else {}
        goods = get_path(detail, "data.goods") or {}
        guige_price = get_path(guige, "data.price") or {}
        recycle_price = as_money(guige_price.get("hs_price_2")) if isinstance(guige_price, dict) else None
        if recycle_price is None and isinstance(guige_price, dict):
            recycle_price = as_money(guige_price.get("hs_price_1"))
        if recycle_price is None:
            raise ParserError("hangzhouxizi missing guige.data.price.hs_price_2")
        return ParsedPrice(
            game_name=str(goods.get("title") or goods.get("name")) if isinstance(goods, dict) and (goods.get("title") or goods.get("name")) is not None else None,
            item_id=str(goods.get("id")) if isinstance(goods, dict) and goods.get("id") is not None else None,
            sku_id=None,
            sell_price=as_money(guige_price.get("price")) if isinstance(guige_price, dict) else None,
            recycle_price=recycle_price,
            parser_note="recycle_price=guige.data.price.hs_price_2",
        )
    if data.get("code") == 0 and data.get("data") is None:
        return ParsedPrice(
            game_name=None,
            item_id=None,
            sku_id=None,
            sell_price=None,
            recycle_price=None,
            status="unavailable",
            parser_note=f"hangzhouxizi {data.get('msg') or '商品不可用'}",
        )
    if data.get("code") == 201 and "uuid" in str(data.get("message", "")).lower():
        raise ParserError("hangzhouxizi requires uuid")
    if data.get("code") == 201 and "系统异常" in str(data.get("message", "")):
        raise ParserError("hangzhouxizi requires a valid uuid")
    if data.get("code") == 99999 and "token" in str(data.get("message", "")).lower():
        return ParsedPrice(
            game_name=None,
            item_id=None,
            sku_id=None,
            sell_price=None,
            recycle_price=None,
            status="skipped",
            parser_note="hangzhouxizi token invalid; refresh XIZI_RECYCLEXCX",
        )
    goods = get_path(data, "data.goods")
    if isinstance(goods, dict):
        name = goods.get("title") or goods.get("name")
        item_id = goods.get("id")
        base_price = as_money(goods.get("price"))
        if base_price is None:
            raise ParserError("hangzhouxizi missing data.goods.price")
        return ParsedPrice(
            game_name=str(name) if name is not None else None,
            item_id=str(item_id) if item_id is not None else None,
            sku_id=None,
            sell_price=base_price,
            recycle_price=base_price,
            parser_note="recycle_price=data.goods.price fallback without guige",
        )
    return parse_generic(data, note="hangzhouxizi parser uses generic field fallback until real response is confirmed")


def parse_buerjia(data: dict[str, Any]) -> ParsedPrice:
    payload = data.get("data") or {}
    if not isinstance(payload, dict):
        raise ParserError("buerjia response missing data object")
    recycle_price = as_money(payload.get("box"))
    if recycle_price is None and any(payload.get(key) is not None for key in ("recyclePrice", "receivePrice", "buybackPrice")):
        return parse_generic(data, note="buerjia parser uses generic recycle field fallback")
    note = "recycle_price=data.box; missing data.notaobao"
    notaobao = as_money(payload.get("notaobao"))
    if recycle_price is not None and notaobao is not None:
        recycle_price += notaobao
        note = "recycle_price=data.box+data.notaobao"
    if recycle_price in (None, 0):
        return ParsedPrice(
            game_name=str(payload.get("name")) if payload.get("name") is not None else None,
            item_id=str(payload.get("id")) if payload.get("id") is not None else None,
            sku_id=None,
            sell_price=as_money(payload.get("nobox")),
            recycle_price=None,
            status="unavailable",
            parser_note="buerjia missing data.box recycle price",
        )
    return ParsedPrice(
        game_name=str(payload.get("name")) if payload.get("name") is not None else None,
        item_id=str(payload.get("id")) if payload.get("id") is not None else None,
        sku_id=None,
        sell_price=as_money(payload.get("nobox")),
        recycle_price=recycle_price,
        parser_note=note,
    )


def parse_baibiandui(data: dict[str, Any]) -> ParsedPrice:
    if data.get("code") not in (None, 0, 200):
        raise ParserError(f"baibiandui API returned code={data.get('code')}")
    payload = data.get("data") or {}
    if not isinstance(payload, dict):
        raise ParserError("baibiandui response missing data object")

    name = payload.get("title") or payload.get("goodsName") or payload.get("name")
    item_id = payload.get("id") or payload.get("goodsId")
    sell_price = as_money(payload.get("replacementSecondHandPrice"))
    if sell_price is None:
        sell_price = as_money(first_value(data, SELL_PRICE_PATHS))

    recycle_price = as_money(payload.get("recycleSecondHandPrice"))
    note = "recycle_price=data.recycleSecondHandPrice"
    if recycle_price is None:
        recycle_price = as_money(payload.get("recycleBareCardPrice"))
        note = "recycle_price=data.recycleBareCardPrice fallback"
    if recycle_price is None:
        raise ParserError("baibiandui missing data.recycleSecondHandPrice")

    return ParsedPrice(
        game_name=str(name) if name is not None else None,
        item_id=str(item_id) if item_id is not None else None,
        sku_id=None,
        sell_price=sell_price,
        recycle_price=recycle_price,
        parser_note=note,
    )


def parse_mogushijian(data: dict[str, Any]) -> ParsedPrice:
    specs = data.get("specList")
    if not isinstance(specs, list):
        raise ParserError("mogushijian missing specList")

    selected = None
    for spec in specs:
        if isinstance(spec, dict) and spec.get("name") == "二手盒装":
            selected = spec
            break
    if selected is None:
        selected = next((spec for spec in specs if isinstance(spec, dict) and spec.get("recyclePrice") is not None), None)
    if selected is None:
        raise ParserError("mogushijian missing boxed second-hand spec")

    recycle_price = as_money(selected.get("recyclePrice"))
    if recycle_price is None:
        raise ParserError("mogushijian missing specList.recyclePrice")

    return ParsedPrice(
        game_name=str(data.get("name")) if data.get("name") is not None else None,
        item_id=str(data.get("cardsId")) if data.get("cardsId") is not None else None,
        sku_id=str(selected.get("withPacket")) if selected.get("withPacket") is not None else None,
        sell_price=as_money(selected.get("buyPrice") or selected.get("price")),
        recycle_price=recycle_price,
        parser_note=f"recycle_price=specList[{selected.get('name') or 'first_available'}].recyclePrice",
    )


PARSERS: dict[str, Callable[[dict[str, Any]], ParsedPrice]] = {
    "laolieren": parse_laolieren,
    "huoqiangshou": parse_huoqiangshou,
    "hailuo": parse_hailuo,
    "hangzhouxizi": parse_hangzhouxizi,
    "buerjia": parse_buerjia,
    "baibiandui": parse_baibiandui,
    "mogushijian": parse_mogushijian,
}
