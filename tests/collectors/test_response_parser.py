import json
from pathlib import Path

import pytest

from redshu_radar.collectors.response_parser import (
    ResponseValidationError,
    parse_product_response,
    parse_sales_text,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("已售123", 123),
        ("1.2万", 12_000),
        ("已售1.2w", 12_000),
        ("1.2W", 12_000),
        ("已售 4,003", 4_003),
    ],
)
def test_parses_sales_text(raw: str, expected: int) -> None:
    assert parse_sales_text(raw) == expected


@pytest.mark.parametrize("raw", ["未知", "-1", "1.2亿"])
def test_rejects_unrecognized_sales_text(raw: str) -> None:
    with pytest.raises(ResponseValidationError, match="销量"):
        parse_sales_text(raw)


def test_parses_complete_success_response() -> None:
    product = parse_product_response(load_fixture("product_success.json"))

    assert product.title == "开学第一课 PPT"
    assert product.shop_id == "shop-1"
    assert product.shop_name == "测试店铺"
    assert product.price_cents == 990
    assert product.sold_reported == 12_000


def test_complete_success_response_may_report_real_zero() -> None:
    product = parse_product_response(load_fixture("product_zero_sales.json"))

    assert product.price_cents == 199
    assert product.sold_reported == 0


def test_rejects_business_error_without_interpreting_zero() -> None:
    with pytest.raises(ResponseValidationError, match="商品不可用"):
        parse_product_response(load_fixture("product_business_error.json"))


def test_rejects_incomplete_success_response() -> None:
    with pytest.raises(ResponseValidationError, match="价格"):
        parse_product_response(load_fixture("product_missing_fields.json"))
