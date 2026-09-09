from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from redshu_radar.storage.database import Database
from redshu_radar.storage.repositories import (
    CollectionRepository,
    ProductRepository,
)


@pytest.fixture
def repositories(tmp_path: Path) -> tuple[ProductRepository, CollectionRepository]:
    database = Database(tmp_path / "radar.sqlite3")
    database.initialize()
    return ProductRepository(database), CollectionRepository(database)


def test_product_insert_is_idempotent(
    repositories: tuple[ProductRepository, CollectionRepository],
) -> None:
    products, _ = repositories
    observed_since = datetime(2026, 9, 9, tzinfo=UTC)

    first_inserted = products.add(
        item_id="a" * 24,
        original_input="分享文案 https://example.com/a",
        source_url="https://example.com/a",
        observed_since=observed_since,
    )
    second_inserted = products.add(
        item_id="a" * 24,
        original_input="a" * 24,
        source_url=None,
        observed_since=observed_since + timedelta(minutes=1),
    )

    assert first_inserted is True
    assert second_inserted is False
    assert [product.item_id for product in products.list_all()] == ["a" * 24]


def test_success_attempt_creates_ordered_trusted_snapshots(
    repositories: tuple[ProductRepository, CollectionRepository],
) -> None:
    products, collections = repositories
    started_at = datetime(2026, 9, 9, tzinfo=UTC)
    products.add("b" * 24, "b" * 24, None, started_at)
    run_id = collections.start_run("manual", started_at)

    collections.record_success(
        run_id=run_id,
        item_id="b" * 24,
        captured_at=started_at + timedelta(minutes=2),
        price_cents=199,
        sold_reported=120,
        title="测试商品",
        shop_id="shop-1",
        shop_name="测试店铺",
        source="public_api",
        response_hash="hash-2",
    )
    collections.record_success(
        run_id=run_id,
        item_id="b" * 24,
        captured_at=started_at + timedelta(minutes=1),
        price_cents=199,
        sold_reported=100,
        title="测试商品",
        shop_id="shop-1",
        shop_name="测试店铺",
        source="public_api",
        response_hash="hash-1",
    )

    snapshots = collections.snapshots_for("b" * 24)
    assert [snapshot.sold_reported for snapshot in snapshots] == [100, 120]
    assert all(attempt.succeeded for attempt in collections.attempts_for(run_id))


def test_failure_attempt_does_not_create_snapshot(
    repositories: tuple[ProductRepository, CollectionRepository],
) -> None:
    products, collections = repositories
    attempted_at = datetime(2026, 9, 9, tzinfo=UTC)
    products.add("c" * 24, "c" * 24, None, attempted_at)
    run_id = collections.start_run("daily", attempted_at)

    collections.record_failure(
        run_id=run_id,
        item_id="c" * 24,
        attempted_at=attempted_at,
        http_status=461,
        error_type="risk_control",
        error_message="HTTP 461",
    )

    assert collections.snapshots_for("c" * 24) == []
    attempts = collections.attempts_for(run_id)
    assert len(attempts) == 1
    assert attempts[0].succeeded is False
    assert attempts[0].http_status == 461
