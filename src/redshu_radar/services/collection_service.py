from dataclasses import dataclass
from datetime import datetime

from redshu_radar.collectors.base import CollectionError, ProductCollector
from redshu_radar.storage.repositories import CollectionRepository, ProductRepository


@dataclass(frozen=True)
class CollectionSummary:
    run_id: int
    success_count: int
    failure_count: int
    status: str


class CollectionService:
    def __init__(
        self,
        products: ProductRepository,
        collections: CollectionRepository,
        collector: ProductCollector,
    ) -> None:
        self.products = products
        self.collections = collections
        self.collector = collector

    def collect_all(self, trigger: str, *, captured_at: datetime) -> CollectionSummary:
        run_id = self.collections.start_run(trigger, captured_at)
        success_count = 0
        failure_count = 0

        for product in self.products.list_all():
            if not product.enabled:
                continue
            try:
                collected = self.collector.collect(product.item_id)
            except CollectionError as exc:
                failure_count += 1
                self.collections.record_failure(
                    run_id=run_id,
                    item_id=product.item_id,
                    attempted_at=captured_at,
                    http_status=exc.http_status,
                    error_type=exc.error_type,
                    error_message=str(exc),
                )
                continue

            normalized = collected.product
            self.collections.record_success(
                run_id=run_id,
                item_id=product.item_id,
                captured_at=captured_at,
                price_cents=normalized.price_cents,
                sold_reported=normalized.sold_reported,
                title=normalized.title,
                shop_id=normalized.shop_id,
                shop_name=normalized.shop_name,
                source=collected.source,
                response_hash=collected.response_hash,
            )
            success_count += 1

        status = self._status(success_count, failure_count)
        self.collections.finish_run(
            run_id,
            finished_at=captured_at,
            success_count=success_count,
            failure_count=failure_count,
            status=status,
        )
        return CollectionSummary(run_id, success_count, failure_count, status)

    @staticmethod
    def _status(success_count: int, failure_count: int) -> str:
        if failure_count == 0:
            return "succeeded"
        if success_count == 0:
            return "failed"
        return "partial"
