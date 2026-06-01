import sqlite3

import pytest

from food_ops_demo.models import OperationPlan, Task
from food_ops_demo.storage import DemoDatabase


def _task(task_id: str, state: str = "awaiting_approval", updated_at: str = "2026-01-01T00:00:00+00:00") -> Task:
    return Task(
        task_id=task_id,
        instruction=f"instruction {task_id}",
        state=state,
        updated_at=updated_at,
        plan=OperationPlan(
            instruction=f"instruction {task_id}",
            operation_type="menu.update_price",
            store_name="人民广场店",
            target_name="招牌牛肉饭",
            changes={"price": "29.90"},
        ),
    )


def test_database_seeds_demo_store(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    snapshot = db.get_store_snapshot("人民广场店")

    assert snapshot.store_name == "人民广场店"
    assert snapshot.phone == "021-88888888"
    assert snapshot.items[0].name == "招牌牛肉饭"
    assert snapshot.items[0].price == "32.00"


def test_database_seeds_exact_demo_data(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    snapshot = db.get_store_snapshot("人民广场店")

    assert snapshot.business_hours == [{"start": "09:30", "end": "21:30"}]
    assert [
        (item.name, item.price, item.sale_status, item.image)
        for item in snapshot.items
    ] == [
        ("招牌牛肉饭", "32.00", "on_sale", "beef_rice.jpg"),
        ("可乐", "6.00", "on_sale", "cola.jpg"),
        ("宫保鸡丁", "28.00", "on_sale", "kung_pao_chicken.jpg"),
    ]


def test_database_raises_key_error_for_unknown_store(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    with pytest.raises(KeyError):
        db.get_store_snapshot("不存在的门店")


def test_database_returns_empty_items_for_unknown_store(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    assert db.find_menu_items("不存在的门店", "招牌牛肉饭") == []


def test_database_persists_menu_price_across_instances(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = DemoDatabase(path)
    first.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    second = DemoDatabase(path)
    item = second.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert item.price == "29.90"


def test_database_update_menu_price_returns_false_for_missing_targets(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    assert db.update_menu_price("人民广场店", "不存在的菜品", "29.90") is False
    assert db.update_menu_price("不存在的门店", "招牌牛肉饭", "29.90") is False


def test_database_persists_menu_sale_status(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = DemoDatabase(path)

    assert first.update_menu_sale_status("人民广场店", "可乐", "sold_out") is True

    second = DemoDatabase(path)
    item = second.find_menu_items("人民广场店", "可乐")[0]
    assert item.sale_status == "sold_out"


def test_database_persists_business_hours_json_round_trip(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = DemoDatabase(path)
    hours = [{"start": "10:00", "end": "22:00"}]

    assert first.update_business_hours("人民广场店", hours) is True

    second = DemoDatabase(path)
    assert second.get_store_snapshot("人民广场店").business_hours == hours


def test_database_persists_store_phone(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = DemoDatabase(path)

    assert first.update_store_phone("人民广场店", "021-66668888") is True

    second = DemoDatabase(path)
    assert second.get_store_snapshot("人民广场店").phone == "021-66668888"


def test_database_reset_restores_seed_data(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    db.reset_demo_data()
    item = db.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert item.price == "32.00"


def test_database_reset_is_repeatable(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    db.reset_demo_data()
    db.reset_demo_data()
    snapshot = db.get_store_snapshot("人民广场店")

    assert [item.name for item in snapshot.items] == ["招牌牛肉饭", "可乐", "宫保鸡丁"]


def test_database_reset_rolls_back_when_seed_insert_fails(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    def fail_seed_insert(*_args):
        raise RuntimeError("seed failed")

    db._insert_seed_data = fail_seed_insert

    with pytest.raises(RuntimeError):
        db.reset_demo_data()

    item = db.find_menu_items("人民广场店", "招牌牛肉饭")[0]
    assert item.price == "29.90"


def test_database_connection_context_closes_connection(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    with db._connect() as conn:
        conn.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_database_save_and_get_task_round_trip(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    task = _task("task_round_trip", state="succeeded")
    task.result = {"verified": True}

    db.save_task(task)
    loaded = db.get_task(task.task_id)

    assert loaded is not None
    assert loaded.task_id == task.task_id
    assert loaded.state == "succeeded"
    assert loaded.result["verified"] is True


def test_database_get_task_returns_none_for_missing_task(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    assert db.get_task("missing_task") is None


def test_database_list_tasks_orders_by_updated_at_and_applies_limit(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    older = _task("task_older", updated_at="2026-01-01T00:00:00+00:00")
    newer = _task("task_newer", updated_at="2026-01-02T00:00:00+00:00")
    newest = _task("task_newest", updated_at="2026-01-03T00:00:00+00:00")

    db.save_task(older)
    db.save_task(newest)
    db.save_task(newer)

    assert [task.task_id for task in db.list_tasks(limit=2)] == ["task_newest", "task_newer"]


def test_database_list_tasks_rejects_negative_limit(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    with pytest.raises(ValueError, match="limit"):
        db.list_tasks(limit=-1)
