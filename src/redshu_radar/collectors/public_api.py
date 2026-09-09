import hashlib
import json
from collections.abc import Sequence
from typing import Any

from redshu_radar.collectors.base import (
    CollectedProduct,
    CollectionError,
    Transport,
)
from redshu_radar.collectors.response_parser import (
    ResponseValidationError,
    parse_product_response,
)
from redshu_radar.collectors.transports import CurlTransport, UrllibTransport


ENDPOINT = (
    "https://mall.xiaohongshu.com/api/store/jpd/edith/detail/h5/toc"
    "?version=0.0.5&item_id={item_id}"
)


class PublicApiCollector:
    def __init__(
        self,
        transports: Sequence[Transport],
        *,
        timeout: float = 10.0,
        max_rounds: int = 2,
    ) -> None:
        if not transports:
            raise ValueError("at least one transport is required")
        if max_rounds < 1:
            raise ValueError("max_rounds must be positive")
        self.transports = tuple(transports)
        self.timeout = timeout
        self.max_rounds = max_rounds

    def url_for(self, item_id: str) -> str:
        return ENDPOINT.format(item_id=item_id)

    def collect(self, item_id: str) -> CollectedProduct:
        last_error: Exception | None = None
        last_http_status: int | None = None
        for _ in range(self.max_rounds):
            for transport in self.transports:
                try:
                    response = transport.get(self.url_for(item_id), self.timeout)
                except (OSError, TimeoutError) as exc:
                    last_error = exc
                    continue

                if response.status == 461:
                    raise CollectionError(
                        "rate_limited", "HTTP 461", http_status=response.status
                    )
                if response.status >= 500:
                    last_http_status = response.status
                    continue
                if response.status != 200:
                    raise CollectionError(
                        "http_error",
                        f"HTTP {response.status}",
                        http_status=response.status,
                    )

                payload = self._decode_payload(response.body)
                if payload.get("success") is not True:
                    message = str(payload.get("msg") or "小红书业务响应失败")
                    raise CollectionError("business_error", message)
                try:
                    product = parse_product_response(payload)
                except ResponseValidationError as exc:
                    raise CollectionError("schema_changed", str(exc)) from exc
                return CollectedProduct(
                    item_id=item_id,
                    product=product,
                    source=transport.name,
                    response_hash=hashlib.sha256(response.body).hexdigest(),
                )

        if last_http_status is not None:
            raise CollectionError(
                "http_error",
                f"HTTP {last_http_status}",
                http_status=last_http_status,
            )
        raise CollectionError("network_error", str(last_error or "network request failed"))

    @staticmethod
    def _decode_payload(body: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectionError("schema_changed", "响应不是有效 JSON") from exc
        if not isinstance(payload, dict):
            raise CollectionError("schema_changed", "响应 JSON 顶层不是对象")
        return payload


def default_public_api_collector() -> PublicApiCollector:
    return PublicApiCollector([UrllibTransport(), CurlTransport()])
