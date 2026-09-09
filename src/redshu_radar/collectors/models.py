from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedProduct:
    title: str
    shop_id: str | None
    shop_name: str
    price_cents: int
    sold_reported: int
