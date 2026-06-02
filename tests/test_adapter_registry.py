from __future__ import annotations

from dataclasses import dataclass

from food_ops_demo.adapter import FakePlatformAdapter
from food_ops_demo.adapter_registry import AdapterRegistry


class ClosableAdapter(FakePlatformAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def close(self) -> None:
        self.closed = True


@dataclass
class AdapterRecorder:
    created: list[ClosableAdapter]

    def factory(self) -> ClosableAdapter:
        adapter = ClosableAdapter()
        self.created.append(adapter)
        return adapter


def test_registry_reuses_shared_fake_adapter():
    fake = FakePlatformAdapter()
    registry = AdapterRegistry({"fake": lambda: fake}, shared_modes={"fake"})

    with registry.use("fake") as first:
        with registry.use("fake") as second:
            assert first is fake
            assert second is fake


def test_registry_closes_scoped_browser_adapter_after_use():
    recorder = AdapterRecorder(created=[])
    registry = AdapterRegistry({"mock_web": recorder.factory}, shared_modes=set())

    with registry.use("mock_web") as adapter:
        assert adapter.closed is False
        first = adapter

    assert first.closed is True
    with registry.use("mock_web") as second:
        assert second is not first
    assert second.closed is True


def test_registry_returns_none_for_unknown_mode():
    registry = AdapterRegistry({}, shared_modes=set())

    assert registry.has_mode("missing") is False
