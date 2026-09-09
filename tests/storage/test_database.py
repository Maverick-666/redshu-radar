import sqlite3
from pathlib import Path

import pytest

from redshu_radar.storage.database import Database


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
    } <= tables


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
