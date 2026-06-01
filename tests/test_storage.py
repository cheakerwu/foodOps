import sqlite3

import pytest

from food_ops_demo.storage import DemoDatabase


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
