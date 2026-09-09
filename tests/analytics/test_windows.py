from datetime import UTC, datetime, timedelta

import pytest

from redshu_radar.analytics.windows import select_baseline
from redshu_radar.domain import Snapshot


NOW = datetime(2026, 9, 9, 0, 2, tzinfo=UTC)


def snapshot(hours_ago: float, sold: int, snapshot_id: int) -> Snapshot:
    return Snapshot(
        id=snapshot_id,
        run_id=snapshot_id,
        item_id="a" * 24,
        captured_at=NOW - timedelta(hours=hours_ago),
        source="public_api",
        price_cents=990,
        sold_reported=sold,
        title="测试商品",
        shop_id="shop-1",
        shop_name="测试店铺",
        response_hash=None,
    )


@pytest.mark.parametrize("hours", [20, 24, 28])
def test_daily_window_includes_confirmed_boundaries(hours: float) -> None:
    current = snapshot(0, 200, 2)
    baseline = snapshot(hours, 100, 1)

    assert select_baseline([baseline, current], 20, 28) == baseline


@pytest.mark.parametrize("hours", [19.99, 28.01])
def test_daily_window_excludes_values_outside_boundaries(hours: float) -> None:
    assert select_baseline([snapshot(hours, 100, 1), snapshot(0, 200, 2)], 20, 28) is None


def test_daily_window_prefers_snapshot_closest_to_24_hours() -> None:
    snapshots = [snapshot(27, 100, 1), snapshot(24, 110, 2), snapshot(1, 190, 3), snapshot(0, 200, 4)]

    assert select_baseline(snapshots, 20, 28).id == 2


def test_hour_window_prefers_snapshot_closest_to_one_hour() -> None:
    snapshots = [snapshot(1.4, 100, 1), snapshot(1, 110, 2), snapshot(0, 130, 3)]

    assert select_baseline(snapshots, 0.75, 1.5).id == 2
