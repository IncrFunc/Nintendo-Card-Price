import pytest

from nsg_price.parsers import PARSERS, ParserError


def test_huoqiangshou_parser_receive_price():
    parsed = PARSERS["huoqiangshou"](
        {
            "detail": {
                "data": {
                    "productId": 1001,
                    "productName": "塞尔达传说 王国之泪",
                    "receivePrice": "218",
                }
            },
            "apprize": {
                "data": {
                    "listProductQuestion": [
                        {"answers": [{}, {"name": "别店购买", "reducePrice": "18"}]}
                    ]
                }
            },
        }
    )
    assert parsed.game_name == "塞尔达传说 王国之泪"
    assert parsed.item_id == "1001"
    assert parsed.recycle_price == 200.0


def test_huoqiangshou_parser_uses_other_shop_answer_by_name():
    parsed = PARSERS["huoqiangshou"](
        {
            "detail": {
                "data": {
                    "productId": 1001,
                    "productName": "塞尔达传说 王国之泪",
                    "receivePrice": "218",
                }
            },
            "apprize": {
                "data": {
                    "listProductQuestion": [
                        {
                            "answers": [
                                {"name": "我店购买", "reducePrice": "10"},
                                {"name": "别店购买", "reducePrice": "18"},
                            ]
                        }
                    ]
                }
            },
        }
    )
    assert parsed.recycle_price == 200.0


def test_huoqiangshou_parser_marks_unavailable_when_other_shop_reduce_missing():
    parsed = PARSERS["huoqiangshou"](
        {
            "detail": {
                "data": {
                    "productId": 1001,
                    "productName": "宝可梦传说 Z-A",
                    "receivePrice": "280",
                    "retailPrice": "300",
                }
            },
            "apprize": {"data": {"listProductQuestion": []}},
        }
    )
    assert parsed.status == "unavailable"
    assert parsed.recycle_price is None
    assert parsed.sell_price == 300.0
    assert parsed.parser_note == "huoqiangshou no other-shop recycle option"


@pytest.mark.parametrize("parser_name", ["hangzhouxizi", "buerjia"])
def test_generic_merchant_parsers_find_recycle_price(parser_name):
    parsed = PARSERS[parser_name](
        {
            "data": {
                "id": "abc-1",
                "name": "马里奥赛车 8 豪华版",
                "price": 260,
                "recyclePrice": 210,
            }
        }
    )
    assert parsed.game_name == "马里奥赛车 8 豪华版"
    assert parsed.item_id == "abc-1"
    assert parsed.recycle_price == 210.0


def test_hangzhouxizi_generic_parser_can_calculate_sell_minus_deduct():
    parsed = PARSERS["hangzhouxizi"](
        {
            "data": {
                "id": "llr-1",
                "name": "超级马力欧 奥德赛",
                "sellPrice": 230,
                "deductPrice": 35,
            }
        }
    )
    assert parsed.recycle_price == 195.0


def test_hangzhouxizi_uses_guige_other_shop_recycle_price():
    parsed = PARSERS["hangzhouxizi"](
        {
            "detail": {
                "code": 1,
                "data": {
                    "goods": {
                        "id": 50,
                        "title": "NS塞尔达传说",
                        "price": 223,
                    }
                },
            },
            "guige": {
                "code": 1,
                "data": {
                    "price": {
                        "price": 223,
                        "hs_price_1": 203,
                        "hs_price_2": 200,
                    }
                }
            },
        }
    )

    assert parsed.game_name == "NS塞尔达传说"
    assert parsed.item_id == "50"
    assert parsed.status == "ok"
    assert parsed.recycle_price == 200.0
    assert parsed.sell_price == 223.0
    assert parsed.parser_note == "recycle_price=guige.data.price.hs_price_2"


def test_hangzhouxizi_uses_hs_price_1_when_hs_price_2_missing():
    parsed = PARSERS["hangzhouxizi"](
        {
            "detail": {
                "code": 1,
                "data": {
                    "goods": {
                        "id": 50,
                        "title": "NS Zelda",
                        "price": 223,
                    }
                },
            },
            "guige": {
                "code": 1,
                "data": {
                    "price": {
                        "price": 223,
                        "hs_price_1": 203,
                    }
                },
            },
        }
    )

    assert parsed.recycle_price == 203.0
    assert parsed.sell_price == 223.0
    assert parsed.parser_note == "recycle_price=guige.data.price.hs_price_1"


def test_hangzhouxizi_falls_back_to_goods_price_when_guige_recycle_price_missing():
    parsed = PARSERS["hangzhouxizi"](
        {
            "detail": {
                "code": 1,
                "data": {
                    "goods": {
                        "id": 50,
                        "title": "NS Zelda",
                        "price": 223,
                    }
                },
            },
            "guige": {"code": 1, "data": {"price": {}}},
        }
    )

    assert parsed.recycle_price == 223.0
    assert parsed.sell_price == 223.0
    assert parsed.parser_note == "recycle_price=detail.data.goods.price fallback"


def test_hangzhouxizi_marks_removed_goods_as_unavailable():
    parsed = PARSERS["hangzhouxizi"]({"code": 0, "msg": "商品已下架", "data": None})

    assert parsed.status == "unavailable"
    assert parsed.recycle_price is None
    assert parsed.parser_note == "hangzhouxizi 商品已下架"


def test_buerjia_parser_uses_box_plus_notaobao_for_other_shop_price():
    parsed = PARSERS["buerjia"](
        {
            "code": 1,
            "data": {
                "id": 3,
                "name": "NS1 塞尔达传说 荒野之息",
                "box": "220.00",
                "nobox": "205.00",
                "taobao": "-20.00",
                "notaobao": "-20.00",
            },
        }
    )

    assert parsed.game_name == "NS1 塞尔达传说 荒野之息"
    assert parsed.item_id == "3"
    assert parsed.sell_price == 205.0
    assert parsed.recycle_price == 200.0
    assert parsed.parser_note == "recycle_price=data.box+data.notaobao"


def test_baibiandui_parser_handles_second_hand_price_fields():
    parsed = PARSERS["baibiandui"](
        {
            "data": {
                "id": "b2",
                "title": "NS1 塞尔达传说 王国之泪",
                "replacementSecondHandPrice": 240,
                "recycleSecondHandPrice": 225,
                "recycleBareCardPrice": 215,
            }
        }
    )
    assert parsed.item_id == "b2"
    assert parsed.sell_price == 240.0
    assert parsed.recycle_price == 225.0


def test_mogushijian_parser_prefers_boxed_recycle_price():
    parsed = PARSERS["mogushijian"](
        {
            "cardsId": 6854,
            "name": "超级马里奥：奥德赛",
            "specList": [
                {"name": "二手盒装", "price": 245, "buyPrice": 245, "recyclePrice": 210, "withPacket": 1},
                {"name": "二手裸卡", "price": 245, "buyPrice": 245, "recyclePrice": 200, "withPacket": 2},
            ],
        }
    )

    assert parsed.game_name == "超级马里奥：奥德赛"
    assert parsed.item_id == "6854"
    assert parsed.sku_id == "1"
    assert parsed.sell_price == 245.0
    assert parsed.recycle_price == 210.0


def test_parser_raises_when_price_missing():
    with pytest.raises(ParserError):
        PARSERS["baibiandui"]({"data": {"id": "x", "name": "No price"}})


def test_hangzhouxizi_parser_reports_invalid_uuid():
    with pytest.raises(ParserError, match="valid uuid"):
        PARSERS["hangzhouxizi"]({"code": 201, "message": "系统异常,请稍后重试", "data": None})


def test_hangzhouxizi_parser_skips_invalid_token():
    parsed = PARSERS["hangzhouxizi"]({"code": 99999, "message": "token invalid", "data": None})
    assert parsed.status == "skipped"
    assert parsed.recycle_price is None
    assert parsed.parser_note == "hangzhouxizi endpoint rejected the request token"


def test_laolieren_parser_matches_demo_formula():
    parsed = PARSERS["laolieren"](
        {
            "row": {
                "id": "154",
                "name": "塞尔达传说 旷野之息",
                "is_outside": "1",
                "price": "100",
                "outside_diff": "20",
            }
        }
    )
    assert parsed.recycle_price == 120.0
    assert parsed.parser_note == "recycle_price=row.price+row.outside_diff"


def test_laolieren_outside_unavailable():
    parsed = PARSERS["laolieren"](
        {
            "row": {
                "id": "154",
                "name": "塞尔达传说 旷野之息",
                "is_outside": "0",
                "price": "100",
                "outside_diff": "20",
            }
        }
    )
    assert parsed.status == "unavailable"
    assert parsed.recycle_price is None


def test_hailuo_parser_matches_demo_formula():
    parsed = PARSERS["hailuo"](
        {
            "data": {
                "storeInfo": {
                    "out_recycle": "1",
                    "price": "180",
                    "out_diff": "25",
                }
            }
        }
    )
    assert parsed.recycle_price == 155.0


def test_hailuo_parser_matches_current_product_detail_shape():
    parsed = PARSERS["hailuo"](
        {
            "status": 200,
            "msg": "success",
            "data": {
                "storeInfo": {
                    "id": 1022,
                    "store_name": "NS 塞尔达传说2 王国之泪",
                    "out_recycle": 1,
                    "price": 225,
                    "out_diff": 20,
                },
                "productValue": {
                    "简体中文,【二手盒装】现货": {
                        "id": 45005,
                        "price": 225,
                        "is_recycle": 1,
                    }
                },
            },
        }
    )
    assert parsed.game_name == "NS 塞尔达传说2 王国之泪"
    assert parsed.item_id == "1022"
    assert parsed.sell_price == 225.0
    assert parsed.recycle_price == 205.0


def test_hailuo_out_recycle_unavailable():
    parsed = PARSERS["hailuo"](
        {
            "data": {
                "storeInfo": {
                    "out_recycle": "0",
                    "price": "180",
                    "out_diff": "25",
                }
            }
        }
    )
    assert parsed.status == "unavailable"
    assert parsed.recycle_price is None
