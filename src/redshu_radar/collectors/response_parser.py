import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from redshu_radar.collectors.models import NormalizedProduct


SALES_PATTERN = re.compile(
    r"(?:已售|销量)?\s*([0-9]+(?:\.[0-9]+)?)\s*([万wW]?)\s*\+?"
)


class ResponseValidationError(ValueError):
    pass


def parse_sales_text(raw: str) -> int:
    normalized = raw.strip().replace(",", "")
    match = SALES_PATTERN.fullmatch(normalized)
    if not match:
        raise ResponseValidationError(f"无法解析销量：{raw!r}")

    amount = Decimal(match.group(1))
    if match.group(2):
        amount *= 10_000
    if amount != amount.to_integral_value():
        raise ResponseValidationError(f"销量不是整数：{raw!r}")
    return int(amount)


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResponseValidationError(f"缺少或无效字段：{field_name}")
    return value


def _price_in_cents(value: Any) -> int:
    if value is None or isinstance(value, bool):
        raise ResponseValidationError("缺少或无效价格")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ResponseValidationError("缺少或无效价格") from exc
    if not amount.is_finite() or amount < 0:
        raise ResponseValidationError("缺少或无效价格")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _product_title(template: Mapping[str, Any]) -> str:
    variants = _mapping(template.get("variantsParams"), "variantsParams")
    entries = variants.get("list")
    if not isinstance(entries, list):
        raise ResponseValidationError("缺少商品名称")
    for entry in entries:
        if not isinstance(entry, Mapping) or entry.get("name") != "商品名称":
            continue
        value = entry.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ResponseValidationError("缺少商品名称")


def parse_product_response(payload: Mapping[str, Any]) -> NormalizedProduct:
    if payload.get("success") is not True:
        message = payload.get("msg")
        raise ResponseValidationError(
            str(message) if message else "小红书业务响应失败"
        )

    data = _mapping(payload.get("data"), "data")
    templates = data.get("template_data")
    if not isinstance(templates, list) or not templates:
        raise ResponseValidationError("缺少或无效字段：template_data")
    template = _mapping(templates[0], "template_data[0]")

    price_data = _mapping(template.get("priceH5"), "priceH5")
    price_cents = _price_in_cents(price_data.get("highlightPrice"))
    sales_text = price_data.get("itemAnalysisDataText")
    if sales_text is None or sales_text == "":
        sold_reported = 0
    elif isinstance(sales_text, str):
        sold_reported = parse_sales_text(sales_text)
    else:
        raise ResponseValidationError("缺少或无效销量")

    seller = _mapping(template.get("sellerH5"), "sellerH5")
    shop_name = seller.get("name")
    if not isinstance(shop_name, str) or not shop_name.strip():
        raise ResponseValidationError("缺少店铺名称")
    shop_id = seller.get("id")
    if shop_id is not None and not isinstance(shop_id, str):
        raise ResponseValidationError("店铺 ID 无效")

    return NormalizedProduct(
        title=_product_title(template),
        shop_id=shop_id,
        shop_name=shop_name.strip(),
        price_cents=price_cents,
        sold_reported=sold_reported,
    )
