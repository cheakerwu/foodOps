from __future__ import annotations

from abc import ABC, abstractmethod

from food_ops_demo.models import ErrorDetail, MenuItem, OperationResult, StoreSnapshot


class BasePlatformAdapter(ABC):
    @abstractmethod
    def get_snapshot(self, store_name: str) -> StoreSnapshot:
        raise NotImplementedError

    @abstractmethod
    def find_menu_items(self, store_name: str, item_name: str) -> list[MenuItem]:
        raise NotImplementedError

    @abstractmethod
    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> OperationResult:
        raise NotImplementedError


class FakePlatformAdapter(BasePlatformAdapter):
    def __init__(self) -> None:
        self._stores: dict[str, StoreSnapshot] = {
            "人民广场店": StoreSnapshot(
                store_id="store_001",
                store_name="人民广场店",
                phone="021-88888888",
                business_hours=[{"start": "09:30", "end": "21:30"}],
                items=[
                    MenuItem(
                        item_id="item_001",
                        store_id="store_001",
                        name="招牌牛肉饭",
                        price="32.00",
                        sale_status="on_sale",
                        image="beef_rice.jpg",
                    ),
                    MenuItem(
                        item_id="item_002",
                        store_id="store_001",
                        name="可乐",
                        price="6.00",
                        sale_status="on_sale",
                        image="cola.jpg",
                    ),
                    MenuItem(
                        item_id="item_003",
                        store_id="store_001",
                        name="宫保鸡丁",
                        price="28.00",
                        sale_status="on_sale",
                        image="kung_pao_chicken.jpg",
                    ),
                ],
            )
        }

    def get_snapshot(self, store_name: str) -> StoreSnapshot:
        store = self._stores.get(store_name)
        if store is None:
            raise KeyError(store_name)
        return store.model_copy(deep=True)

    def find_menu_items(self, store_name: str, item_name: str) -> list[MenuItem]:
        store = self._stores.get(store_name)
        if store is None:
            return []
        return [item.model_copy(deep=True) for item in store.items if item.name == item_name]

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> OperationResult:
        item = self._find_single_internal(store_name, item_name)
        if item is None:
            return _not_found()
        item.price = price
        return OperationResult(success=True)

    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> OperationResult:
        item = self._find_single_internal(store_name, item_name)
        if item is None:
            return _not_found()
        item.sale_status = sale_status
        return OperationResult(success=True)

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> OperationResult:
        store = self._stores.get(store_name)
        if store is None:
            return OperationResult(
                success=False,
                error=ErrorDetail(code="store_not_found", message=f"找不到门店：{store_name}"),
            )
        store.business_hours = business_hours
        return OperationResult(success=True)

    def _find_single_internal(self, store_name: str, item_name: str) -> MenuItem | None:
        store = self._stores.get(store_name)
        if store is None:
            return None
        matches = [item for item in store.items if item.name == item_name]
        if len(matches) != 1:
            return None
        return matches[0]


def _not_found() -> OperationResult:
    return OperationResult(
        success=False,
        error=ErrorDetail(code="target_not_found", message="找不到目标菜品。"),
    )
