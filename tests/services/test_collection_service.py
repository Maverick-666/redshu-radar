from datetime import UTC, datetime
from pathlib import Path

from redshu_radar.collectors.base import CollectedProduct, CollectionError
from redshu_radar.collectors.models import NormalizedProduct
from redshu_radar.services.collection_service import CollectionService
from redshu_radar.storage.database import Database
from redshu_radar.storage.repositories import CollectionRepository, ProductRepository


class FakeCollector:
    def __init__(self, outcomes: dict[str, CollectedProduct | CollectionError]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    def collect(self, item_id: str) -> CollectedProduct:
        self.calls.append(item_id)
        outcome = self.outcomes[item_id]
        if isinstance(outcome, CollectionError):
            raise outcome
        return outcome


def collected(item_id: str, sold: int) -> CollectedProduct:
    return CollectedProduct(
        item_id=item_id,
        product=NormalizedProduct(
            title=f"商品 {item_id[0]}",
            shop_id="shop-1",
            shop_name="测试店铺",
            price_cents=990,
            sold_reported=sold,
        ),
        source="public_api",
        response_hash=f"hash-{item_id[0]}",
    )


def test_batch_continues_after_one_product_fails(tmp_path: Path) -> None:
    now = datetime(2026, 9, 9, 0, 2, tzinfo=UTC)
    database = Database(tmp_path / "radar.sqlite3")
    database.initialize()
    products = ProductRepository(database)
    collections = CollectionRepository(database)
    products.add("a" * 24, "a" * 24, None, now)
    products.add("b" * 24, "b" * 24, None, now)
    collector = FakeCollector(
        {
            "a" * 24: collected("a" * 24, 100),
            "b" * 24: CollectionError(
                "rate_limited", "HTTP 461", http_status=461
            ),
        }
    )
    service = CollectionService(products, collections, collector)

    summary = service.collect_all("daily", captured_at=now)

    assert summary.success_count == 1
    assert summary.failure_count == 1
    assert summary.status == "partial"
    assert collector.calls == ["a" * 24, "b" * 24]
    assert len(collections.snapshots_for("a" * 24)) == 1
    assert collections.snapshots_for("b" * 24) == []
    attempts = collections.attempts_for(summary.run_id)
    assert [attempt.succeeded for attempt in attempts] == [True, False]


def test_reported_sales_rollback_keeps_trusted_high_water(tmp_path: Path) -> None:
    now = datetime(2026, 9, 9, 0, 2, tzinfo=UTC)
    database = Database(tmp_path / "radar.sqlite3")
    database.initialize()
    products = ProductRepository(database)
    collections = CollectionRepository(database)
    products.add("c" * 24, "c" * 24, None, now)
    service = CollectionService(
        products,
        collections,
        FakeCollector({"c" * 24: collected("c" * 24, 120)}),
    )
    service.collect_all("manual", captured_at=now)
    service = CollectionService(
        products,
        collections,
        FakeCollector({"c" * 24: collected("c" * 24, 100)}),
    )

    service.collect_all("manual", captured_at=now.replace(hour=1))

    assert [
        snapshot.sold_reported for snapshot in collections.snapshots_for("c" * 24)
    ] == [120, 100]
    assert collections.trusted_high_water("c" * 24) == 120


def test_rate_limit_stops_the_rest_of_the_batch(tmp_path: Path) -> None:
    now = datetime(2026, 9, 9, 0, 2, tzinfo=UTC)
    database = Database(tmp_path / "radar.sqlite3")
    database.initialize()
    products = ProductRepository(database)
    collections = CollectionRepository(database)
    for item_id in ("a" * 24, "b" * 24, "c" * 24):
        products.add(item_id, item_id, None, now)
    collector = FakeCollector(
        {
            "a" * 24: CollectionError(
                "rate_limited", "HTTP 461", http_status=461
            ),
            "b" * 24: collected("b" * 24, 100),
            "c" * 24: collected("c" * 24, 100),
        }
    )

    summary = CollectionService(products, collections, collector).collect_all(
        "daily", captured_at=now
    )

    assert collector.calls == ["a" * 24]
    assert summary.failure_count == 1
    assert summary.status == "failed"
