from datetime import UTC, datetime, timedelta

from redshu_radar.analytics.metrics import calculate_metrics
from redshu_radar.analytics.ranking import rank_products
from redshu_radar.domain import Snapshot


NOW = datetime(2026, 9, 9, 0, 2, tzinfo=UTC)


def snapshots(item_id: str, baseline: int, current: int, price_cents: int) -> list[Snapshot]:
    return [
        Snapshot(1, 1, item_id, NOW - timedelta(hours=24), "public_api", price_cents, baseline, "商品", None, "店铺", None),
        Snapshot(2, 2, item_id, NOW, "public_api", price_cents, current, "商品", None, "店铺", None),
    ]


def test_ranking_excludes_incomplete_products_and_sorts_stably() -> None:
    high = calculate_metrics(snapshots("b" * 24, 100, 300, 990))
    low = calculate_metrics(snapshots("a" * 24, 100, 200, 990))
    incomplete = calculate_metrics(snapshots("c" * 24, 100, 200, 990)[1:])

    ranked = rank_products([low, incomplete, high])

    assert [item.item_id for item in ranked] == ["b" * 24, "a" * 24]
