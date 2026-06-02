from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from food_ops_demo.adapter import BasePlatformAdapter


AdapterFactory = Callable[[], BasePlatformAdapter]


class AdapterRegistry:
    def __init__(self, factories: dict[str, AdapterFactory], shared_modes: set[str] | None = None) -> None:
        self._factories = factories
        self._shared_modes = shared_modes or set()
        self._shared_adapters: dict[str, BasePlatformAdapter] = {}

    def has_mode(self, mode: str) -> bool:
        return mode in self._factories

    @contextmanager
    def use(self, mode: str) -> Iterator[BasePlatformAdapter | None]:
        factory = self._factories.get(mode)
        if factory is None:
            yield None
            return

        if mode in self._shared_modes:
            adapter = self._shared_adapters.get(mode)
            if adapter is None:
                adapter = factory()
                self._shared_adapters[mode] = adapter
            yield adapter
            return

        adapter = factory()
        try:
            yield adapter
        finally:
            close = getattr(adapter, "close", None)
            if callable(close):
                close()
