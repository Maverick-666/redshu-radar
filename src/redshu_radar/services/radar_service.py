from dataclasses import asdict
from pathlib import Path

from redshu_radar.analytics.metrics import ProductMetrics, calculate_metrics
from redshu_radar.analytics.ranking import rank_products
from redshu_radar.domain import Product, Snapshot
from redshu_radar.storage.repositories import (
    CategoryRepository,
    CollectionRepository,
    ProductRepository,
    TagRepository,
)


class RadarService:
    def __init__(
        self,
        products: ProductRepository,
        collections: CollectionRepository,
        categories: CategoryRepository,
        tags: TagRepository,
        database_path: Path,
    ) -> None:
        self.products = products
        self.collections = collections
        self.categories = categories
        self.tags = tags
        self.database_path = database_path

    def status(self) -> dict[str, object]:
        latest_run = self.collections.latest_run()
        return {
            "product_count": self.products.count(),
            "snapshot_count": self.collections.snapshot_count(),
            "database_bytes": self.database_path.stat().st_size,
            "last_collection": asdict(latest_run) if latest_run else None,
        }

    def list_products(self) -> list[dict[str, object]]:
        entries = [
            (product, self.collections.snapshots_for(product.item_id))
            for product in self.products.list_all()
        ]
        metrics = {
            product.item_id: calculate_metrics(snapshots)
            for product, snapshots in entries
            if snapshots
        }
        payloads = {
            product.item_id: self._product_payload(
                product,
                snapshots,
                metrics.get(product.item_id),
            )
            for product, snapshots in entries
        }
        ranked_ids = [
            item.item_id
            for item in rank_products(
                [
                    metrics[item_id]
                    for item_id, payload in payloads.items()
                    if payload["data_status"] == "complete_daily"
                ]
            )
        ]
        ranked_set = set(ranked_ids)
        ordered_ids = ranked_ids + [
            product.item_id
            for product, _ in entries
            if product.item_id not in ranked_set
        ]
        return [payloads[item_id] for item_id in ordered_ids]

    def product_detail(self, item_id: str) -> dict[str, object] | None:
        product = self.products.get(item_id)
        if product is None:
            return None
        snapshots = self.collections.snapshots_for(item_id)
        metrics = calculate_metrics(snapshots) if snapshots else None
        payload = self._product_payload(product, snapshots, metrics)
        payload["snapshots"] = [
            asdict(snapshot) for snapshot in snapshots
        ]
        payload["failures"] = [
            asdict(attempt) for attempt in self.collections.failures_for(item_id)
        ]
        return payload

    def _product_payload(
        self,
        product: Product,
        snapshots: list[Snapshot],
        metrics: ProductMetrics | None,
    ) -> dict[str, object]:
        payload = asdict(product)
        category = (
            self.categories.get(product.category_id)
            if product.category_id is not None
            else None
        )
        track = (
            self.categories.get(category.parent_id)
            if category is not None and category.parent_id is not None
            else None
        )
        payload["track"] = (
            {"id": track.id, "name": track.name} if track is not None else None
        )
        payload["subcategory"] = (
            {"id": category.id, "name": category.name}
            if category is not None
            else None
        )
        payload["tags"] = [
            {"id": tag.id, "name": tag.name}
            for tag in self.tags.list_for_product(product.item_id)
        ]
        if not snapshots:
            payload.update(
                {
                    "data_status": "awaiting_baseline",
                    "trusted_high_water": None,
                    "sales_delta": None,
                    "hourly_delta": None,
                    "hotness": None,
                    "product_value": None,
                    "baseline_snapshot_id": None,
                    "current_snapshot_id": None,
                }
            )
            self._apply_latest_error(payload, product.item_id, None)
            return payload

        if metrics is None:
            raise ValueError("snapshots require metrics")
        payload.update(asdict(metrics))
        payload["data_status"] = payload.pop("status")
        latest = snapshots[-1]
        payload.update(
            {
                "title": latest.title,
                "shop_id": latest.shop_id,
                "shop_name": latest.shop_name,
                "price_cents": latest.price_cents,
            }
        )
        self._apply_latest_error(payload, product.item_id, latest)
        return payload

    def _apply_latest_error(
        self,
        payload: dict[str, object],
        item_id: str,
        latest_snapshot: Snapshot | None,
    ) -> None:
        attempt = self.collections.latest_attempt_for(item_id)
        payload["last_error"] = None
        if (
            attempt is not None
            and not attempt.succeeded
            and (
                latest_snapshot is None
                or attempt.attempted_at >= latest_snapshot.captured_at
            )
        ):
            payload["data_status"] = "collection_error"
            payload["last_error"] = asdict(attempt)
