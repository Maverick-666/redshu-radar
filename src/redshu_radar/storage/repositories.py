from datetime import datetime

from redshu_radar.domain import CollectionAttempt, Product, Snapshot
from redshu_radar.storage.database import Database


def _as_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.isoformat()


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


class ProductRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(
        self,
        item_id: str,
        original_input: str,
        source_url: str | None,
        observed_since: datetime,
    ) -> bool:
        timestamp = _as_iso(observed_since)
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO products (
                    item_id, original_input, source_url, observed_since,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    original_input,
                    source_url,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
        return cursor.rowcount == 1

    def list_all(self) -> list[Product]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM products ORDER BY observed_since, item_id"
            ).fetchall()
        return [
            Product(
                item_id=row["item_id"],
                original_input=row["original_input"],
                source_url=row["source_url"],
                observed_since=_as_datetime(row["observed_since"]),
                enabled=bool(row["enabled"]),
                decision_status=row["decision_status"],
                title=row["title"],
                shop_id=row["shop_id"],
                shop_name=row["shop_name"],
            )
            for row in rows
        ]


class CollectionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def start_run(self, trigger: str, started_at: datetime) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO collection_runs (trigger, started_at) VALUES (?, ?)",
                (trigger, _as_iso(started_at)),
            )
        return int(cursor.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        finished_at: datetime,
        success_count: int,
        failure_count: int,
        status: str,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE collection_runs
                SET finished_at = ?, success_count = ?, failure_count = ?, status = ?
                WHERE id = ?
                """,
                (
                    _as_iso(finished_at),
                    success_count,
                    failure_count,
                    status,
                    run_id,
                ),
            )

    def record_success(
        self,
        *,
        run_id: int,
        item_id: str,
        captured_at: datetime,
        price_cents: int,
        sold_reported: int,
        title: str,
        shop_id: str | None,
        shop_name: str,
        source: str,
        response_hash: str | None,
    ) -> None:
        timestamp = _as_iso(captured_at)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO collection_attempts (
                    run_id, item_id, attempted_at, succeeded, http_status
                ) VALUES (?, ?, ?, 1, 200)
                """,
                (run_id, item_id, timestamp),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO snapshots (
                    run_id, item_id, captured_at, source, price_cents,
                    sold_reported, title, shop_id, shop_name, response_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item_id,
                    timestamp,
                    source,
                    price_cents,
                    sold_reported,
                    title,
                    shop_id,
                    shop_name,
                    response_hash,
                ),
            )
            connection.execute(
                """
                UPDATE products
                SET title = ?, shop_id = ?, shop_name = ?, updated_at = ?
                WHERE item_id = ?
                """,
                (title, shop_id, shop_name, timestamp, item_id),
            )

    def record_failure(
        self,
        *,
        run_id: int,
        item_id: str,
        attempted_at: datetime,
        http_status: int | None,
        error_type: str,
        error_message: str,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO collection_attempts (
                    run_id, item_id, attempted_at, succeeded,
                    http_status, error_type, error_message
                ) VALUES (?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    run_id,
                    item_id,
                    _as_iso(attempted_at),
                    http_status,
                    error_type,
                    error_message,
                ),
            )

    def snapshots_for(self, item_id: str) -> list[Snapshot]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM snapshots
                WHERE item_id = ?
                ORDER BY captured_at, id
                """,
                (item_id,),
            ).fetchall()
        return [
            Snapshot(
                id=row["id"],
                run_id=row["run_id"],
                item_id=row["item_id"],
                captured_at=_as_datetime(row["captured_at"]),
                source=row["source"],
                price_cents=row["price_cents"],
                sold_reported=row["sold_reported"],
                title=row["title"],
                shop_id=row["shop_id"],
                shop_name=row["shop_name"],
                response_hash=row["response_hash"],
            )
            for row in rows
        ]

    def attempts_for(self, run_id: int) -> list[CollectionAttempt]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM collection_attempts
                WHERE run_id = ?
                ORDER BY attempted_at, id
                """,
                (run_id,),
            ).fetchall()
        return [
            CollectionAttempt(
                id=row["id"],
                run_id=row["run_id"],
                item_id=row["item_id"],
                attempted_at=_as_datetime(row["attempted_at"]),
                succeeded=bool(row["succeeded"]),
                http_status=row["http_status"],
                error_type=row["error_type"],
                error_message=row["error_message"],
            )
            for row in rows
        ]

    def trusted_high_water(self, item_id: str) -> int | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT MAX(sold_reported) FROM snapshots WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        return row[0] if row and row[0] is not None else None
