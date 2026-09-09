from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Product:
    item_id: str
    original_input: str
    source_url: str | None
    observed_since: datetime
    enabled: bool
    decision_status: str
    title: str | None
    shop_id: str | None
    shop_name: str | None


@dataclass(frozen=True)
class Snapshot:
    id: int
    run_id: int
    item_id: str
    captured_at: datetime
    source: str
    price_cents: int
    sold_reported: int
    title: str
    shop_id: str | None
    shop_name: str
    response_hash: str | None


@dataclass(frozen=True)
class CollectionAttempt:
    id: int
    run_id: int
    item_id: str
    attempted_at: datetime
    succeeded: bool
    http_status: int | None
    error_type: str | None
    error_message: str | None
