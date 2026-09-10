import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from redshu_radar.domain import Product
from redshu_radar.storage.database import Database
from redshu_radar.storage.repositories import ProductRepository


LEGACY_SCHEMA = """
CREATE TABLE products (
    item_id TEXT PRIMARY KEY,
    original_input TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    shop_id TEXT,
    shop_name TEXT,
    observed_since TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    decision_status TEXT NOT NULL DEFAULT 'watching',
    audience TEXT,
    scenario TEXT,
    problem TEXT,
    delivery TEXT,
    notes TEXT,
    next_action TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running'
);
CREATE TABLE collection_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES products(item_id) ON DELETE CASCADE,
    attempted_at TEXT NOT NULL,
    succeeded INTEGER NOT NULL,
    http_status INTEGER,
    error_type TEXT,
    error_message TEXT
);
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL REFERENCES products(item_id) ON DELETE CASCADE,
    captured_at TEXT NOT NULL,
    source TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    sold_reported INTEGER NOT NULL,
    title TEXT NOT NULL,
    shop_id TEXT,
    shop_name TEXT NOT NULL,
    response_hash TEXT,
    UNIQUE (item_id, captured_at, source)
);
"""


def _create_seeded_old_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            """
            INSERT INTO products (
                item_id, original_input, title, observed_since,
                enabled, decision_status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "z" * 24,
                "旧商品输入",
                "旧商品",
                "2026-09-01T00:00:00+00:00",
                0,
                "reviewing",
                "保留人工判断",
                "2026-09-01T00:00:00+00:00",
                "2026-09-02T00:00:00+00:00",
            ),
        )
        run_id = connection.execute(
            """
            INSERT INTO collection_runs (
                trigger, started_at, finished_at, success_count, status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "manual",
                "2026-09-02T00:00:00+00:00",
                "2026-09-02T00:01:00+00:00",
                1,
                "succeeded",
            ),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO snapshots (
                run_id, item_id, captured_at, source, price_cents,
                sold_reported, title, shop_id, shop_name, response_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "z" * 24,
                "2026-09-02T00:00:30+00:00",
                "public_api",
                990,
                42,
                "旧商品",
                "shop-old",
                "旧店铺",
                "old-hash",
            ),
        )


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "radar.sqlite3")
    database.initialize()
    return database


def test_database_enables_wal_and_foreign_keys(database: Database) -> None:
    with database.connect() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert journal_mode == "wal"
    assert foreign_keys == 1


def test_database_creates_required_tables(database: Database) -> None:
    with database.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "products",
        "collection_runs",
        "collection_attempts",
        "snapshots",
        "categories",
        "tags",
        "product_tags",
    } <= tables


def test_initialize_upgrades_seeded_old_database_without_data_loss(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "old-radar.sqlite3"
    _create_seeded_old_database(database_path)

    Database(database_path).initialize()

    with sqlite3.connect(database_path) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("products", "collection_runs", "snapshots")
        }
        product = connection.execute(
            """
            SELECT item_id, title, enabled, decision_status, notes, category_id
            FROM products
            """
        ).fetchone()
        snapshot = connection.execute(
            """
            SELECT sold_reported, price_cents, response_hash
            FROM snapshots
            """
        ).fetchone()

    assert counts == {"products": 1, "collection_runs": 1, "snapshots": 1}
    assert product == (
        "z" * 24,
        "旧商品",
        0,
        "reviewing",
        "保留人工判断",
        None,
    )
    assert snapshot == (42, 990, "old-hash")


def test_initialize_is_idempotent_and_adds_category_column_once(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "old-radar.sqlite3"
    _create_seeded_old_database(database_path)
    database = Database(database_path)

    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO categories (
                name, normalized_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            ("内容创作", "内容创作", "2026-09-10", "2026-09-10"),
        )
    database.initialize()

    with database.connect() as connection:
        category_columns = [
            row[1]
            for row in connection.execute("PRAGMA table_info(products)")
            if row[1] == "category_id"
        ]
        category_count = connection.execute(
            "SELECT COUNT(*) FROM categories"
        ).fetchone()[0]

    assert category_columns == ["category_id"]
    assert category_count == 1


def test_initialize_rolls_back_all_taxonomy_changes_when_migration_fails(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "old-radar.sqlite3"
    broken_migration = tmp_path / "broken-taxonomy.sql"
    _create_seeded_old_database(database_path)
    broken_migration.write_text(
        "CREATE TABLE categories (id INTEGER PRIMARY KEY);\nBROKEN SQL;",
        encoding="utf-8",
    )
    database = Database(database_path)
    database.taxonomy_migration_path = broken_migration

    with pytest.raises(sqlite3.OperationalError):
        database.initialize()

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        product_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(products)")
        }
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("products", "collection_runs", "snapshots")
        }

    assert "categories" not in tables
    assert "tags" not in tables
    assert "product_tags" not in tables
    assert "category_id" not in product_columns
    assert counts == {"products": 1, "collection_runs": 1, "snapshots": 1}


def test_custom_migration_path_keeps_single_script_behavior(tmp_path: Path) -> None:
    database_path = tmp_path / "custom.sqlite3"
    migration_path = tmp_path / "custom.sql"
    migration_path.write_text(
        "CREATE TABLE custom_only (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )

    Database(database_path, migration_path=migration_path).initialize()

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert "custom_only" in tables
    assert "categories" not in tables
    assert "tags" not in tables


def test_taxonomy_schema_has_foreign_keys_unique_constraints_and_indexes(
    database: Database,
) -> None:
    with database.connect() as connection:
        category_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(categories)")
        }
        tag_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tags)")
        }
        product_tag_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(product_tags)")
        }
        category_foreign_keys = {
            (row[2], row[3], row[4])
            for row in connection.execute("PRAGMA foreign_key_list(categories)")
        }
        product_foreign_keys = {
            (row[2], row[3], row[4])
            for row in connection.execute("PRAGMA foreign_key_list(products)")
        }
        product_tag_foreign_keys = {
            (row[2], row[3], row[4])
            for row in connection.execute("PRAGMA foreign_key_list(product_tags)")
        }
        indexes = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'index' AND name NOT LIKE 'sqlite_autoindex%'
                """
            )
        }

    assert category_columns == {
        "id",
        "name",
        "normalized_name",
        "parent_id",
        "created_at",
        "updated_at",
    }
    assert tag_columns == {
        "id",
        "name",
        "normalized_name",
        "created_at",
        "updated_at",
    }
    assert product_tag_columns == {"product_id", "tag_id"}
    assert ("categories", "parent_id", "id") in category_foreign_keys
    assert ("categories", "category_id", "id") in product_foreign_keys
    assert product_tag_foreign_keys == {
        ("products", "product_id", "item_id"),
        ("tags", "tag_id", "id"),
    }
    assert {
        "idx_categories_parent",
        "idx_categories_root_normalized_name",
        "idx_categories_child_normalized_name",
        "idx_products_category",
        "idx_tags_normalized_name",
        "idx_product_tags_tag",
    } <= indexes


def test_taxonomy_unique_constraints_reject_duplicate_associations(
    database: Database,
) -> None:
    with database.connect() as connection:
        timestamp = "2026-09-10T00:00:00+00:00"
        connection.execute(
            "INSERT INTO categories (name, normalized_name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            ("AI 教程", "ai 教程", timestamp, timestamp),
        )
        root_id = connection.execute(
            "SELECT id FROM categories WHERE parent_id IS NULL"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO categories "
            "(name, normalized_name, parent_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("提示词", "提示词", root_id, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO tags (name, normalized_name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            ("开学季", "开学季", timestamp, timestamp),
        )
        tag_id = connection.execute("SELECT id FROM tags").fetchone()[0]
        connection.execute(
            "INSERT INTO products "
            "(item_id, original_input, observed_since, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("u" * 24, "input", timestamp, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO product_tags (product_id, tag_id) VALUES (?, ?)",
            ("u" * 24, tag_id),
        )

        duplicate_statements = [
            (
                "INSERT INTO categories "
                "(name, normalized_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("重复赛道", "ai 教程", timestamp, timestamp),
            ),
            (
                "INSERT INTO categories "
                "(name, normalized_name, parent_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("重复细分", "提示词", root_id, timestamp, timestamp),
            ),
            (
                "INSERT INTO tags (name, normalized_name, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                ("重复标签", "开学季", timestamp, timestamp),
            ),
            (
                "INSERT INTO product_tags (product_id, tag_id) VALUES (?, ?)",
                ("u" * 24, tag_id),
            ),
        ]
        for statement, parameters in duplicate_statements:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement, parameters)


def test_product_legacy_keyword_construction_defaults_category_to_none() -> None:
    product = Product(
        item_id="p" * 24,
        original_input="input",
        source_url=None,
        observed_since=datetime(2026, 9, 10, tzinfo=UTC),
        enabled=True,
        decision_status="watching",
        title=None,
        shop_id=None,
        shop_name=None,
        audience=None,
        scenario=None,
        problem=None,
        delivery=None,
        notes=None,
        next_action=None,
    )

    assert product.category_id is None


def test_existing_product_reads_with_no_category(tmp_path: Path) -> None:
    database_path = tmp_path / "old-radar.sqlite3"
    _create_seeded_old_database(database_path)
    database = Database(database_path)
    database.initialize()

    product = ProductRepository(database).get("z" * 24)

    assert product is not None
    assert product.category_id is None


def test_snapshot_rejects_negative_sales(database: Database) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO products (
                item_id, original_input, observed_since, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "a" * 24,
                "a" * 24,
                "2026-09-09T00:00:00+00:00",
                "2026-09-09T00:00:00+00:00",
                "2026-09-09T00:00:00+00:00",
            ),
        )
        run_id = connection.execute(
            "INSERT INTO collection_runs (trigger, started_at) VALUES (?, ?)",
            ("manual", "2026-09-09T00:00:00+00:00"),
        ).lastrowid

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO snapshots (
                    run_id, item_id, captured_at, source,
                    price_cents, sold_reported, title, shop_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    "a" * 24,
                    "2026-09-09T00:00:01+00:00",
                    "public_api",
                    199,
                    -1,
                    "测试商品",
                    "测试店铺",
                ),
            )
