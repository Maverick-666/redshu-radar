import json
from pathlib import Path

import pytest

from redshu_radar.collectors.base import CollectionError, HttpResponse
from redshu_radar.collectors.public_api import PublicApiCollector


ITEM_ID = "6a37ecb45200e70001a2b26a"
FIXTURES = Path(__file__).parents[1] / "fixtures"


class FakeTransport:
    def __init__(self, name: str, outcomes: list[HttpResponse | Exception]) -> None:
        self.name = name
        self.outcomes = outcomes
        self.calls = 0

    def get(self, url: str, timeout: float) -> HttpResponse:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def fixture_response(name: str, status: int = 200) -> HttpResponse:
    body = (FIXTURES / name).read_bytes()
    return HttpResponse(status=status, body=body)


def test_falls_back_to_second_direct_transport() -> None:
    first = FakeTransport("urllib", [OSError("timed out")])
    second = FakeTransport("curl", [fixture_response("product_success.json")])
    collector = PublicApiCollector([first, second], max_rounds=1)

    result = collector.collect(ITEM_ID)

    assert first.calls == 1
    assert second.calls == 1
    assert result.source == "curl"
    assert result.product.sold_reported == 12_000
    assert len(result.response_hash) == 64


def test_transient_failures_stop_after_configured_rounds() -> None:
    transport = FakeTransport(
        "urllib",
        [OSError("first"), OSError("second")],
    )
    collector = PublicApiCollector([transport], max_rounds=2)

    with pytest.raises(CollectionError) as error:
        collector.collect(ITEM_ID)

    assert transport.calls == 2
    assert error.value.error_type == "network_error"


def test_http_461_stops_without_trying_fallback() -> None:
    first = FakeTransport("urllib", [HttpResponse(status=461, body=b"")])
    second = FakeTransport("curl", [fixture_response("product_success.json")])
    collector = PublicApiCollector([first, second], max_rounds=2)

    with pytest.raises(CollectionError) as error:
        collector.collect(ITEM_ID)

    assert error.value.error_type == "rate_limited"
    assert error.value.http_status == 461
    assert first.calls == 1
    assert second.calls == 0


def test_business_failure_is_not_retried() -> None:
    response = fixture_response("product_business_error.json")
    transport = FakeTransport("urllib", [response, response])
    collector = PublicApiCollector([transport], max_rounds=2)

    with pytest.raises(CollectionError) as error:
        collector.collect(ITEM_ID)

    assert error.value.error_type == "business_error"
    assert transport.calls == 1


def test_invalid_json_is_reported_as_schema_error() -> None:
    transport = FakeTransport("urllib", [HttpResponse(status=200, body=b"not-json")])
    collector = PublicApiCollector([transport], max_rounds=1)

    with pytest.raises(CollectionError) as error:
        collector.collect(ITEM_ID)

    assert error.value.error_type == "schema_changed"


def test_request_url_contains_only_the_item_id() -> None:
    transport = FakeTransport("urllib", [fixture_response("product_success.json")])
    collector = PublicApiCollector([transport], max_rounds=1)

    collector.collect(ITEM_ID)

    # A real transport receives the URL; this checks the public endpoint contract separately.
    assert collector.url_for(ITEM_ID).endswith(f"item_id={ITEM_ID}")
    assert json.loads((FIXTURES / "product_success.json").read_text())["success"] is True
