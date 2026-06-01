from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from food_ops_demo.models import ErrorDetail, OperationPlan, ParseResult


PRICE_PATTERN = re.compile(r"^把(?P<store>.+?店)的(?P<target>.+?)改成\s*(?P<price>\d+(?:\.\d+)?)$")
SALE_STATUS_PATTERN = re.compile(r"^把(?P<store>.+?店)的(?P<target>.+?)(?P<action>下架|上架)$")
BUSINESS_HOURS_PATTERN = re.compile(
    r"^把(?P<store>.+?店)营业时间改成\s*(?P<start>\d{1,2}(?::\d{2})?)\s*到\s*(?P<end>\d{1,2}(?::\d{2})?)$"
)
PHONE_PATTERN = re.compile(r"^把(?P<store>.+?店)(?:联系电话|电话)改成\s*(?P<phone>[0-9\-]{7,20})$")


def parse_instruction(text: str) -> ParseResult:
    instruction = " ".join(text.strip().split())
    if not instruction:
        return _error("empty_instruction", "请输入要执行的运营指令。")

    if match := PRICE_PATTERN.match(instruction):
        price = _format_price(match.group("price"))
        if price is None:
            return _error("invalid_price", "价格格式不正确。")
        return ParseResult(
            plan=OperationPlan(
                instruction=instruction,
                operation_type="menu.update_price",
                store_name=match.group("store"),
                target_name=match.group("target"),
                changes={"price": price},
            )
        )

    if match := SALE_STATUS_PATTERN.match(instruction):
        status = "off_sale" if match.group("action") == "下架" else "on_sale"
        return ParseResult(
            plan=OperationPlan(
                instruction=instruction,
                operation_type="menu.update_sale_status",
                store_name=match.group("store"),
                target_name=match.group("target"),
                changes={"sale_status": status},
            )
        )

    if match := BUSINESS_HOURS_PATTERN.match(instruction):
        return ParseResult(
            plan=OperationPlan(
                instruction=instruction,
                operation_type="store.update_business_hours",
                store_name=match.group("store"),
                changes={
                    "business_hours": [
                        {"start": _format_time(match.group("start")), "end": _format_time(match.group("end"))}
                    ]
                },
            )
        )

    if match := PHONE_PATTERN.match(instruction):
        return ParseResult(
            plan=OperationPlan(
                instruction=instruction,
                operation_type="store.update_phone",
                store_name=match.group("store"),
                changes={"phone": match.group("phone")},
            )
        )

    return _error("unsupported_instruction", "暂不支持该指令，请使用改价、上下架或营业时间修改指令。")


def _format_price(value: str) -> str | None:
    try:
        price = Decimal(value)
    except InvalidOperation:
        return None
    return str(price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _format_time(value: str) -> str:
    if ":" in value:
        hour, minute = value.split(":", 1)
    else:
        hour, minute = value, "00"
    return f"{int(hour):02d}:{int(minute):02d}"


def _error(code: str, message: str) -> ParseResult:
    return ParseResult(errors=[ErrorDetail(code=code, message=message)])
