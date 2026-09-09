from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from redshu_radar.analytics.windows import select_baseline
from redshu_radar.domain import Snapshot


TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class ProductMetrics:
    item_id: str
    status: str
    current_snapshot_id: int
    baseline_snapshot_id: int | None
    interval_hours: Decimal | None
    sales_delta: int | None
    hourly_delta: int | None
    trusted_high_water: int
    daily_average: Decimal | None
    hotness: Decimal | None
    product_value: Decimal | None


def _hours_between(current: Snapshot, baseline: Snapshot) -> Decimal:
    seconds = Decimal(str((current.captured_at - baseline.captured_at).total_seconds()))
    return (seconds / Decimal(3600)).quantize(TWO_PLACES)


def _high_water_at(snapshots: list[Snapshot], target: Snapshot) -> int:
    return max(
        snapshot.sold_reported
        for snapshot in snapshots
        if snapshot.captured_at <= target.captured_at
    )


def _ranking_metrics(
    current: Snapshot,
    high_water: int,
    sales_delta: int,
) -> tuple[Decimal | None, Decimal | None]:
    if sales_delta <= 0:
        product_value = Decimal("0.00") if sales_delta == 0 else None
        return None, product_value
    if high_water <= 0:
        return None, None
    hotness = (Decimal(high_water) / Decimal(sales_delta)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    price = Decimal(current.price_cents) / Decimal(100)
    product_value = (
        price
        * Decimal(sales_delta)
        * (Decimal(sales_delta) / Decimal(high_water))
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return hotness, product_value


def calculate_metrics(snapshots: list[Snapshot]) -> ProductMetrics:
    if not snapshots:
        raise ValueError("at least one snapshot is required")
    ordered = sorted(snapshots, key=lambda snapshot: (snapshot.captured_at, snapshot.id))
    current = ordered[-1]
    high_water = max(snapshot.sold_reported for snapshot in ordered)

    if len(ordered) == 1:
        return ProductMetrics(
            current.item_id,
            "awaiting_baseline",
            current.id,
            None,
            None,
            None,
            None,
            high_water,
            None,
            None,
            None,
        )

    prior_high_water = max(snapshot.sold_reported for snapshot in ordered[:-1])
    if current.sold_reported < prior_high_water:
        return ProductMetrics(
            current.item_id,
            "rollback_suspected",
            current.id,
            None,
            None,
            None,
            None,
            high_water,
            None,
            None,
            None,
        )

    hourly_baseline = select_baseline(ordered, 0.75, 1.5)
    hourly_delta = (
        high_water - _high_water_at(ordered, hourly_baseline)
        if hourly_baseline is not None
        else None
    )
    daily_baseline = select_baseline(ordered, 20, 28)
    if daily_baseline is not None:
        sales_delta = high_water - _high_water_at(ordered, daily_baseline)
        hotness, product_value = _ranking_metrics(current, high_water, sales_delta)
        return ProductMetrics(
            current.item_id,
            "complete_daily",
            current.id,
            daily_baseline.id,
            _hours_between(current, daily_baseline),
            sales_delta,
            hourly_delta,
            high_water,
            None,
            hotness,
            product_value,
        )

    baseline = ordered[-2]
    interval_hours = _hours_between(current, baseline)
    sales_delta = high_water - _high_water_at(ordered, baseline)
    if interval_hours > Decimal(28):
        daily_average = (
            Decimal(sales_delta) * Decimal(24) / interval_hours
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return ProductMetrics(
            current.item_id,
            "cross_period",
            current.id,
            baseline.id,
            interval_hours,
            sales_delta,
            hourly_delta,
            high_water,
            daily_average,
            None,
            None,
        )

    return ProductMetrics(
        current.item_id,
        "partial",
        current.id,
        baseline.id,
        interval_hours,
        sales_delta,
        hourly_delta,
        high_water,
        None,
        None,
        None,
    )
