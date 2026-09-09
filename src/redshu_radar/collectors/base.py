from dataclasses import dataclass
from typing import Protocol

from redshu_radar.collectors.models import NormalizedProduct


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


@dataclass(frozen=True)
class CollectedProduct:
    item_id: str
    product: NormalizedProduct
    source: str
    response_hash: str


class CollectionError(RuntimeError):
    def __init__(
        self,
        error_type: str,
        message: str,
        *,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.http_status = http_status


class Transport(Protocol):
    name: str

    def get(self, url: str, timeout: float) -> HttpResponse: ...


class ProductCollector(Protocol):
    def collect(self, item_id: str) -> CollectedProduct: ...
