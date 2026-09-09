from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redshu_radar.analytics.metrics import calculate_metrics
from redshu_radar.domain import Snapshot


NOW = datetime(2026, 9, 9, 0, 2, tzinfo=UTC)


def snapshot(hours_ago: float, sold: int, snapshot_id: int, price_cents: int = 990) -> Snapshot:
    return Snapshot(
        id=snapshot_id,
        run_id=snapshot_id,
        item_id="a" * 24,
        captured_at=NOW - timedelta(hours=hours_ago),
        source="public_api",
        price_cents=price_cents,
        sold_reported=sold,
        title="测试商品",
        shop_id="shop-1",
        shop_name="测试店铺",
        response_hash=None,
    )


def test_complete_daily_metrics_include_source_snapshots() -> None:
    baseline = snapshot(24, 1_000, 1)
    hourly = snapshot(1, 1_180, 2)
    current = snapshot(0, 1_200, 3)

    metrics = calculate_metrics([baseline, hourly, current])

    assert metrics.status == "complete_daily"
    assert metrics.baseline_snapshot_id == 1
    assert metrics.current_snapshot_id == 3
    assert metrics.interval_hours == Decimal("24.00")
    assert metrics.sales_delta == 200
    assert metrics.hourly_delta == 20
    assert metrics.trusted_high_water == 1_200
    assert metrics.hotness == Decimal("6.00")
    assert metrics.product_value == Decimal("330.00")


def test_first_snapshot_awaits_baseline() -> None:
    metrics = calculate_metrics([snapshot(0, 100, 1)])

    assert metrics.status == "awaiting_baseline"
    assert metrics.sales_delta is None
    assert metrics.hotness is None
    assert metrics.product_value is None


def test_cross_period_reports_total_and_daily_average_but_no_ranking_metrics() -> None:
    metrics = calculate_metrics([snapshot(48, 1_000, 1), snapshot(0, 1_480, 2)])

    assert metrics.status == "cross_period"
    assert metrics.sales_delta == 480
    assert metrics.interval_hours == Decimal("48.00")
    assert metrics.daily_average == Decimal("240.00")
    assert metrics.hotness is None
    assert metrics.product_value is None


def test_recent_snapshots_without_daily_baseline_are_partial() -> None:
    metrics = calculate_metrics([snapshot(1, 100, 1), snapshot(0, 120, 2)])

    assert metrics.status == "partial"
    assert metrics.sales_delta == 20
    assert metrics.hourly_delta == 20
    assert metrics.daily_average is None


def test_reported_rollback_uses_high_water_and_flags_anomaly() -> None:
    metrics = calculate_metrics([snapshot(24, 100, 1), snapshot(1, 120, 2), snapshot(0, 110, 3)])

    assert metrics.status == "rollback_suspected"
    assert metrics.trusted_high_water == 120
    assert metrics.sales_delta is None
    assert metrics.hotness is None


def test_zero_daily_sales_avoids_division_by_zero() -> None:
    metrics = calculate_metrics([snapshot(24, 100, 1), snapshot(0, 100, 2)])

    assert metrics.status == "complete_daily"
    assert metrics.sales_delta == 0
    assert metrics.hotness is None
    assert metrics.product_value == Decimal("0.00")
