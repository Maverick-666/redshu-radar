from redshu_radar.analytics.metrics import ProductMetrics


def rank_products(metrics: list[ProductMetrics]) -> list[ProductMetrics]:
    eligible = [
        item
        for item in metrics
        if item.status == "complete_daily" and item.product_value is not None
    ]
    return sorted(
        eligible,
        key=lambda item: (-item.product_value, item.item_id),
    )
