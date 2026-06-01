from food_ops_demo.storage import DemoDatabase


def test_database_seeds_demo_store(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")

    snapshot = db.get_store_snapshot("人民广场店")

    assert snapshot.store_name == "人民广场店"
    assert snapshot.phone == "021-88888888"
    assert snapshot.items[0].name == "招牌牛肉饭"
    assert snapshot.items[0].price == "32.00"


def test_database_persists_menu_price_across_instances(tmp_path):
    path = tmp_path / "demo.sqlite3"
    first = DemoDatabase(path)
    first.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    second = DemoDatabase(path)
    item = second.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert item.price == "29.90"


def test_database_reset_restores_seed_data(tmp_path):
    db = DemoDatabase(tmp_path / "demo.sqlite3")
    db.update_menu_price("人民广场店", "招牌牛肉饭", "29.90")

    db.reset_demo_data()
    item = db.find_menu_items("人民广场店", "招牌牛肉饭")[0]

    assert item.price == "32.00"
