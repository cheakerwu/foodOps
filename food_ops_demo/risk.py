from __future__ import annotations

from decimal import Decimal

from food_ops_demo.adapter import BasePlatformAdapter
from food_ops_demo.models import ErrorDetail, OperationPlan, ValidationResult


def validate_plan(plan: OperationPlan | None, adapter: BasePlatformAdapter) -> ValidationResult:
    if plan is None:
        return _error("invalid_plan", "没有可校验的操作计划。")

    try:
        snapshot = adapter.get_snapshot(plan.store_name)
    except KeyError:
        return _error("store_not_found", f"找不到门店：{plan.store_name}")

    if plan.operation_type == "menu.update_price":
        return _validate_price_update(plan, adapter)
    if plan.operation_type == "menu.update_sale_status":
        return _validate_sale_status(plan, adapter)
    if plan.operation_type == "store.update_business_hours":
        validated = plan.model_copy(update={"risk_level": "high", "requires_approval": True})
        return ValidationResult(
            plan=validated,
            preview={
                "operation_type": plan.operation_type,
                "store_name": snapshot.store_name,
                "current_business_hours": snapshot.business_hours,
                "target_business_hours": plan.changes["business_hours"],
            },
        )
    if plan.operation_type == "store.update_phone":
        validated = plan.model_copy(update={"risk_level": "high", "requires_approval": True})
        return ValidationResult(
            plan=validated,
            preview={
                "operation_type": plan.operation_type,
                "store_name": snapshot.store_name,
                "current_phone": snapshot.phone,
                "target_phone": plan.changes["phone"],
                "risk_level": "high",
            },
        )

    return _error("unsupported_operation", f"暂不支持操作类型：{plan.operation_type}")


def _validate_price_update(plan: OperationPlan, adapter: BasePlatformAdapter) -> ValidationResult:
    item_result = _single_item(plan, adapter)
    if isinstance(item_result, ValidationResult):
        return item_result
    item = item_result

    target_price = Decimal(plan.changes["price"])
    if target_price < Decimal("1.00"):
        return _error("price_too_low", "价格不能低于 1 元。")

    current_price = Decimal(item.price)
    change_ratio = abs(target_price - current_price) / current_price if current_price else Decimal("1")
    risk_level = "high" if change_ratio > Decimal("0.5") else "medium"
    validated = plan.model_copy(update={"risk_level": risk_level, "requires_approval": True})
    return ValidationResult(
        plan=validated,
        preview={
            "operation_type": plan.operation_type,
            "store_name": plan.store_name,
            "target_name": item.name,
            "current_price": item.price,
            "target_price": plan.changes["price"],
            "risk_level": risk_level,
        },
    )


def _validate_sale_status(plan: OperationPlan, adapter: BasePlatformAdapter) -> ValidationResult:
    item_result = _single_item(plan, adapter)
    if isinstance(item_result, ValidationResult):
        return item_result
    item = item_result

    validated = plan.model_copy(update={"risk_level": "medium", "requires_approval": True})
    return ValidationResult(
        plan=validated,
        preview={
            "operation_type": plan.operation_type,
            "store_name": plan.store_name,
            "target_name": item.name,
            "current_sale_status": item.sale_status,
            "target_sale_status": plan.changes["sale_status"],
            "risk_level": "medium",
        },
    )


def _single_item(plan: OperationPlan, adapter: BasePlatformAdapter):
    matches = adapter.find_menu_items(plan.store_name, plan.target_name or "")
    if not matches:
        return _error("target_not_found", f"找不到菜品：{plan.target_name}")
    if len(matches) > 1:
        return _error("target_ambiguous", f"找到多个同名菜品：{plan.target_name}")
    return matches[0]


def _error(code: str, message: str) -> ValidationResult:
    return ValidationResult(errors=[ErrorDetail(code=code, message=message)])
