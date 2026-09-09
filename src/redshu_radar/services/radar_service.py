from dataclasses import asdict
from pathlib import Path

from redshu_radar.analytics.metrics import calculate_metrics
from redshu_radar.domain import Product
from redshu_radar.storage.repositories import CollectionRepository, ProductRepository


class RadarService:
    def __init__(
        self,
        products: ProductRepository,
        collections: CollectionRepository,
        database_path: Path,
    ) -> None:
        self.products = products
        self.collections = collections
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
        return [self._product_payload(product) for product in self.products.list_all()]

    def product_detail(self, item_id: str) -> dict[str, object] | None:
        product = self.products.get(item_id)
        if product is None:
            return None
        payload = self._product_payload(product)
        payload["snapshots"] = [
            asdict(snapshot) for snapshot in self.collections.snapshots_for(item_id)
        ]
        return payload

    def _product_payload(self, product: Product) -> dict[str, object]:
        payload = asdict(product)
        snapshots = self.collections.snapshots_for(product.item_id)
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
            return payload

        metrics = calculate_metrics(snapshots)
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
        return payload
