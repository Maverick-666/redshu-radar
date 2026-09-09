import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from redshu_radar.collectors.base import HttpResponse
from redshu_radar.collectors.public_api import PublicApiCollector
from redshu_radar.config import Settings
from redshu_radar.storage.database import Database
from redshu_radar.storage.repositories import CollectionRepository
from redshu_radar.web.app import create_app


ITEM_ID = "6a37ecb45200e70001a2b26a"
FIXTURE = Path(__file__).parents[1] / "fixtures" / "product_success.json"


class SequenceTransport:
    name = "fixture"

    def __init__(self, outcomes: list[HttpResponse | Exception]) -> None:
        self.outcomes = outcomes

    def get(self, url: str, timeout: float) -> HttpResponse:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


def fixture_response(sold_text: str) -> HttpResponse:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["data"]["template_data"][0]["priceH5"][
        "itemAnalysisDataText"
    ] = sold_text
    return HttpResponse(
        status=200,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def request(app, method: str, path: str, **kwargs: object) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_fixture_pipeline_reaches_dashboard_with_complete_daily_metrics(
    tmp_path: Path,
) -> None:
    clock = MutableClock(datetime(2026, 9, 8, 0, 2, tzinfo=UTC))
    collector = PublicApiCollector(
        [SequenceTransport([fixture_response("已售1.2万"), fixture_response("已售1.21万")])],
        max_rounds=1,
    )
    app = create_app(Settings(data_dir=tmp_path), collector=collector, clock=clock)

    imported = request(
        app, "POST", "/api/products/import", json={"input_text": ITEM_ID}
    )
    first = request(app, "POST", "/api/collections", json={"trigger": "manual"})
    clock.current += timedelta(hours=24)
    second = request(app, "POST", "/api/collections", json={"trigger": "daily"})
    product = request(app, "GET", "/api/products").json()[0]
    detail = request(app, "GET", f"/api/products/{ITEM_ID}").json()
    status = request(app, "GET", "/api/status").json()
    page = request(app, "GET", "/")

    assert imported.json()[0]["status"] == "ready"
    assert first.json()["status"] == "succeeded"
    assert second.json()["status"] == "succeeded"
    assert product["data_status"] == "complete_daily"
    assert product["sales_delta"] == 100
    assert product["baseline_snapshot_id"] is not None
    assert product["current_snapshot_id"] is not None
    assert len(detail["snapshots"]) == 2
    assert status["snapshot_count"] == 2
    assert page.status_code == 200
    assert "竞品监控看板" in page.text


def test_network_failure_is_recorded_without_creating_snapshot(tmp_path: Path) -> None:
    now = datetime(2026, 9, 8, 0, 2, tzinfo=UTC)
    collector = PublicApiCollector(
        [SequenceTransport([OSError("offline")])], max_rounds=1
    )
    app = create_app(Settings(data_dir=tmp_path), collector=collector, clock=lambda: now)
    request(app, "POST", "/api/products/import", json={"input_text": ITEM_ID})

    run = request(app, "POST", "/api/collections", json={"trigger": "recovery"})
    status = request(app, "GET", "/api/status").json()
    database = Database(tmp_path / "redshu-radar.sqlite3")
    attempts = CollectionRepository(database).attempts_for(run.json()["run_id"])

    assert run.json()["status"] == "failed"
    assert status["snapshot_count"] == 0
    assert len(attempts) == 1
    assert attempts[0].error_type == "network_error"


def test_cross_period_and_rollback_states_are_consistent_through_api(
    tmp_path: Path,
) -> None:
    clock = MutableClock(datetime(2026, 9, 8, 0, 2, tzinfo=UTC))
    collector = PublicApiCollector(
        [
            SequenceTransport(
                [
                    fixture_response("已售1.2万"),
                    fixture_response("已售1.21万"),
                    fixture_response("已售1.19万"),
                ]
            )
        ],
        max_rounds=1,
    )
    app = create_app(Settings(data_dir=tmp_path), collector=collector, clock=clock)
    request(app, "POST", "/api/products/import", json={"input_text": ITEM_ID})
    request(app, "POST", "/api/collections", json={"trigger": "manual"})

    clock.current += timedelta(hours=30)
    request(app, "POST", "/api/collections", json={"trigger": "recovery"})
    cross_period = request(app, "GET", "/api/products").json()[0]

    clock.current += timedelta(hours=1)
    request(app, "POST", "/api/collections", json={"trigger": "hourly"})
    rollback = request(app, "GET", "/api/products").json()[0]

    assert cross_period["data_status"] == "cross_period"
    assert cross_period["sales_delta"] == 100
    assert cross_period["daily_average"] == "80.00"
    assert cross_period["hotness"] is None
    assert rollback["data_status"] == "rollback_suspected"
    assert rollback["trusted_high_water"] == 12_100
    assert rollback["sales_delta"] is None
