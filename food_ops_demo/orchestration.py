from __future__ import annotations

from pydantic import BaseModel, Field

from food_ops_demo.models import OperationPlan, new_id


class StorePriceChange(BaseModel):
    store_name: str
    item_name: str
    price: str


class BatchPriceChange(BaseModel):
    batch_id: str = Field(default_factory=lambda: new_id("batch"))
    instruction: str
    platform_account_id: str
    changes: list[StorePriceChange]


def build_child_plans(batch: BatchPriceChange) -> list[OperationPlan]:
    return [
        OperationPlan(
            instruction=batch.instruction,
            operation_type="menu.update_price",
            store_name=change.store_name,
            target_name=change.item_name,
            changes={"price": change.price},
            risk_level="medium",
            requires_approval=True,
        )
        for change in batch.changes
    ]


def lock_key_for_plan(platform_account_id: str, plan: OperationPlan) -> str:
    return f"{platform_account_id}:{plan.store_name}"
