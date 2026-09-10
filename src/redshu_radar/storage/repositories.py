from datetime import datetime

from redshu_radar.domain import (
    Category,
    CollectionAttempt,
    CollectionRun,
    Product,
    Snapshot,
    Tag,
)
from redshu_radar.storage.database import Database


def _as_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return value.isoformat()


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _product_from_row(row: object) -> Product:
    return Product(
        item_id=row["item_id"],
        original_input=row["original_input"],
        source_url=row["source_url"],
        observed_since=_as_datetime(row["observed_since"]),
        enabled=bool(row["enabled"]),
        decision_status=row["decision_status"],
        category_id=row["category_id"],
        title=row["title"],
        shop_id=row["shop_id"],
        shop_name=row["shop_name"],
        audience=row["audience"],
        scenario=row["scenario"],
        problem=row["problem"],
        delivery=row["delivery"],
        notes=row["notes"],
        next_action=row["next_action"],
    )


def _category_from_row(row: object) -> Category:
    return Category(
        id=row["id"],
        name=row["name"],
        normalized_name=row["normalized_name"],
        parent_id=row["parent_id"],
        created_at=_as_datetime(row["created_at"]),
        updated_at=_as_datetime(row["updated_at"]),
    )


def _tag_from_row(row: object) -> Tag:
    return Tag(
        id=row["id"],
        name=row["name"],
        normalized_name=row["normalized_name"],
        created_at=_as_datetime(row["created_at"]),
        updated_at=_as_datetime(row["updated_at"]),
    )


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
        return [_product_from_row(row) for row in rows]

    def get(self, item_id: str) -> Product | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM products WHERE item_id = ?", (item_id,)
            ).fetchone()
        return _product_from_row(row) if row is not None else None

    def count(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM products").fetchone()
        return int(row[0])

    def update_decision(
        self,
        item_id: str,
        *,
        decision_status: str,
        audience: str | None,
        scenario: str | None,
        problem: str | None,
        delivery: str | None,
        notes: str | None,
        next_action: str | None,
        updated_at: datetime,
    ) -> Product | None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE products
                SET decision_status = ?, audience = ?, scenario = ?, problem = ?,
                    delivery = ?, notes = ?, next_action = ?, updated_at = ?
                WHERE item_id = ?
                """,
                (
                    decision_status,
                    audience,
                    scenario,
                    problem,
                    delivery,
                    notes,
                    next_action,
                    _as_iso(updated_at),
                    item_id,
                ),
            )
        return self.get(item_id)

    def replace_taxonomy(
        self,
        item_id: str,
        *,
        category_id: int | None,
        tag_ids: list[int],
    ) -> str | None:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            product_exists = connection.execute(
                "SELECT 1 FROM products WHERE item_id = ?", (item_id,)
            ).fetchone()
            if product_exists is None:
                return "product"
            if category_id is not None:
                category = connection.execute(
                    "SELECT parent_id FROM categories WHERE id = ?",
                    (category_id,),
                ).fetchone()
                if category is None or category["parent_id"] is None:
                    return "category"
            if tag_ids:
                placeholders = ", ".join("?" for _ in tag_ids)
                tag_count = connection.execute(
                    f"SELECT COUNT(*) FROM tags WHERE id IN ({placeholders})",
                    tag_ids,
                ).fetchone()[0]
                if tag_count != len(tag_ids):
                    return "tags"
            connection.execute(
                "UPDATE products SET category_id = ? WHERE item_id = ?",
                (category_id, item_id),
            )
            connection.execute(
                "DELETE FROM product_tags WHERE product_id = ?", (item_id,)
            )
            connection.executemany(
                "INSERT INTO product_tags (product_id, tag_id) VALUES (?, ?)",
                [(item_id, tag_id) for tag_id in tag_ids],
            )
        return None


class CategoryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(
        self,
        *,
        name: str,
        normalized_name: str,
        parent_id: int | None,
        created_at: datetime,
    ) -> Category:
        timestamp = _as_iso(created_at)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO categories (
                    name, normalized_name, parent_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (name, normalized_name, parent_id, timestamp, timestamp),
            )
            row = connection.execute(
                """
                SELECT * FROM categories
                WHERE normalized_name = ? AND parent_id IS ?
                """,
                (normalized_name, parent_id),
            ).fetchone()
        if row is None:
            raise RuntimeError("category insert did not produce a row")
        return _category_from_row(row)

    def get(self, category_id: int) -> Category | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
        return _category_from_row(row) if row is not None else None

    def list_all(self) -> list[Category]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM categories ORDER BY id"
            ).fetchall()
        return [_category_from_row(row) for row in rows]


class TagRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(
        self,
        *,
        name: str,
        normalized_name: str,
        created_at: datetime,
    ) -> Tag:
        timestamp = _as_iso(created_at)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO tags (
                    name, normalized_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (name, normalized_name, timestamp, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM tags WHERE normalized_name = ?",
                (normalized_name,),
            ).fetchone()
        if row is None:
            raise RuntimeError("tag insert did not produce a row")
        return _tag_from_row(row)

    def get(self, tag_id: int) -> Tag | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tags WHERE id = ?", (tag_id,)
            ).fetchone()
        return _tag_from_row(row) if row is not None else None

    def list_all(self) -> list[Tag]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM tags ORDER BY id").fetchall()
        return [_tag_from_row(row) for row in rows]

    def list_for_product(self, item_id: str) -> list[Tag]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT tags.* FROM tags
                JOIN product_tags ON product_tags.tag_id = tags.id
                WHERE product_tags.product_id = ?
                ORDER BY tags.id
                """,
                (item_id,),
            ).fetchall()
        return [_tag_from_row(row) for row in rows]


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
        return [self._attempt_from_row(row) for row in rows]

    def latest_attempt_for(self, item_id: str) -> CollectionAttempt | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM collection_attempts
                WHERE item_id = ?
                ORDER BY attempted_at DESC, id DESC
                LIMIT 1
                """,
                (item_id,),
            ).fetchone()
        return self._attempt_from_row(row) if row is not None else None

    def failures_for(
        self, item_id: str, *, limit: int = 20
    ) -> list[CollectionAttempt]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM collection_attempts
                WHERE item_id = ? AND succeeded = 0
                ORDER BY attempted_at DESC, id DESC
                LIMIT ?
                """,
                (item_id, limit),
            ).fetchall()
        return [self._attempt_from_row(row) for row in rows]

    @staticmethod
    def _attempt_from_row(row: object) -> CollectionAttempt:
        return CollectionAttempt(
            id=row["id"],
            run_id=row["run_id"],
            item_id=row["item_id"],
            attempted_at=_as_datetime(row["attempted_at"]),
            succeeded=bool(row["succeeded"]),
            http_status=row["http_status"],
            error_type=row["error_type"],
            error_message=row["error_message"],
        )

    def trusted_high_water(self, item_id: str) -> int | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT MAX(sold_reported) FROM snapshots WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        return row[0] if row and row[0] is not None else None

    def snapshot_count(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()
        return int(row[0])

    def latest_run(self) -> CollectionRun | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM collection_runs ORDER BY started_at DESC, id DESC LIMIT 1"
            ).fetchone()
        return self._run_from_row(row)

    def latest_successful_run(self) -> CollectionRun | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM collection_runs
                WHERE status = 'succeeded' AND success_count > 0
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return self._run_from_row(row)

    @staticmethod
    def _run_from_row(row: object | None) -> CollectionRun | None:
        if row is None:
            return None
        return CollectionRun(
            id=row["id"],
            trigger=row["trigger"],
            started_at=_as_datetime(row["started_at"]),
            finished_at=(
                _as_datetime(row["finished_at"]) if row["finished_at"] else None
            ),
            success_count=row["success_count"],
            failure_count=row["failure_count"],
            status=row["status"],
        )
