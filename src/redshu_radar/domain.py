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
    audience: str | None
    scenario: str | None
    problem: str | None
    delivery: str | None
    notes: str | None
    next_action: str | None
    category_id: int | None = None


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    normalized_name: str
    parent_id: int | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Tag:
    id: int
    name: str
    normalized_name: str
    created_at: datetime
    updated_at: datetime


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


@dataclass(frozen=True)
class CollectionRun:
    id: int
    trigger: str
    started_at: datetime
    finished_at: datetime | None
    success_count: int
    failure_count: int
    status: str
