from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path

from food_ops_demo.models import MenuItem, StoreSnapshot, Task


SEED_STORE_ID = "store_001"
SEED_STORE_NAME = "人民广场店"
SEED_BUSINESS_HOURS = [{"start": "09:30", "end": "21:30"}]
SEED_MENU_ITEMS = [
    ("item_001", SEED_STORE_ID, "招牌牛肉饭", "32.00", "on_sale", "beef_rice.jpg", 1),
    ("item_002", SEED_STORE_ID, "可乐", "6.00", "on_sale", "cola.jpg", 2),
    ("item_003", SEED_STORE_ID, "宫保鸡丁", "28.00", "on_sale", "kung_pao_chicken.jpg", 3),
]


class DemoDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._seed_if_empty()

    def get_store_snapshot(self, store_name: str) -> StoreSnapshot:
        with self._connect() as conn:
            store = conn.execute(
                """
                SELECT store_id, store_name, phone, business_hours_json
                FROM stores
                WHERE store_name = ?
                """,
                (store_name,),
            ).fetchone()
            if store is None:
                raise KeyError(store_name)

            rows = conn.execute(
                """
                SELECT item_id, store_id, name, price, sale_status, image
                FROM menu_items
                WHERE store_id = ?
                ORDER BY sort_order
                """,
                (store["store_id"],),
            ).fetchall()

        return StoreSnapshot(
            store_id=store["store_id"],
            store_name=store["store_name"],
            phone=store["phone"],
            business_hours=json.loads(store["business_hours_json"]),
            items=[MenuItem(**dict(row)) for row in rows],
        )

    def find_menu_items(self, store_name: str, item_name: str) -> list[MenuItem]:
        try:
            snapshot = self.get_store_snapshot(store_name)
        except KeyError:
            return []
        return [item for item in snapshot.items if item.name == item_name]

    def update_menu_price(self, store_name: str, item_name: str, price: str) -> bool:
        return self._update_menu_field(store_name, item_name, "price", price)

    def update_menu_sale_status(self, store_name: str, item_name: str, sale_status: str) -> bool:
        return self._update_menu_field(store_name, item_name, "sale_status", sale_status)

    def update_business_hours(self, store_name: str, business_hours: list[dict[str, str]]) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE stores
                SET business_hours_json = ?
                WHERE store_name = ?
                """,
                (json.dumps(business_hours, ensure_ascii=False), store_name),
            )
            return cursor.rowcount == 1

    def update_store_phone(self, store_name: str, phone: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE stores
                SET phone = ?
                WHERE store_name = ?
                """,
                (phone, store_name),
            )
            return cursor.rowcount == 1

    def reset_demo_data(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM menu_items")
            conn.execute("DELETE FROM stores")
            self._insert_seed_data(conn)

    def save_task(self, task: Task) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (task_id, task_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    task_json = excluded.task_json,
                    updated_at = excluded.updated_at
                """,
                (task.task_id, task.model_dump_json(), task.updated_at),
            )

    def get_task(self, task_id: str) -> Task | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT task_json
                FROM tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        return Task.model_validate_json(row["task_json"]) if row else None

    def list_tasks(self, limit: int = 20) -> list[Task]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT task_json
                FROM tasks
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [Task.model_validate_json(row["task_json"]) for row in rows]

    def _update_menu_field(self, store_name: str, item_name: str, field: str, value: str) -> bool:
        if field not in {"price", "sale_status"}:
            raise ValueError(field)

        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                UPDATE menu_items
                SET {field} = ?
                WHERE store_id = (
                    SELECT store_id FROM stores WHERE store_name = ?
                )
                AND name = ?
                """,
                (value, store_name, item_name),
            )
            return cursor.rowcount == 1

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stores (
                    store_id TEXT PRIMARY KEY,
                    store_name TEXT NOT NULL UNIQUE,
                    phone TEXT NOT NULL,
                    business_hours_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS menu_items (
                    item_id TEXT PRIMARY KEY,
                    store_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price TEXT NOT NULL,
                    sale_status TEXT NOT NULL,
                    image TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    FOREIGN KEY (store_id) REFERENCES stores(store_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _seed_if_empty(self) -> None:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
            if count == 0:
                self._insert_seed_data(conn)

    def _insert_seed_data(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            INSERT INTO stores (store_id, store_name, phone, business_hours_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                SEED_STORE_ID,
                SEED_STORE_NAME,
                "021-88888888",
                json.dumps(SEED_BUSINESS_HOURS, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        conn.executemany(
            """
            INSERT INTO menu_items (
                item_id, store_id, name, price, sale_status, image, sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            SEED_MENU_ITEMS,
        )
