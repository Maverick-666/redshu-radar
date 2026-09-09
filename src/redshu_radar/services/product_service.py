from dataclasses import replace
from datetime import datetime

from redshu_radar.parsing.item_input import BatchInputResult, parse_batch_inputs
from redshu_radar.storage.repositories import ProductRepository


class ProductService:
    def __init__(self, products: ProductRepository) -> None:
        self.products = products

    def import_inputs(
        self, raw_input: str, *, observed_at: datetime
    ) -> list[BatchInputResult]:
        parsed = parse_batch_inputs(raw_input)
        results: list[BatchInputResult] = []
        for item in parsed:
            if item.status != "ready" or item.item_id is None:
                results.append(item)
                continue
            inserted = self.products.add(
                item.item_id,
                item.original_input,
                item.source_url,
                observed_at,
            )
            results.append(
                item
                if inserted
                else replace(item, status="duplicate", message="商品已在选品库")
            )
        return results
