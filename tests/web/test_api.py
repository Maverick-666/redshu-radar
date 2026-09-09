import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI

from redshu_radar.collectors.base import CollectedProduct, CollectionError
from redshu_radar.collectors.models import NormalizedProduct
from redshu_radar.config import Settings
from redshu_radar.web.app import create_app


NOW = datetime(2026, 9, 9, 0, 2, tzinfo=UTC)
ITEM_ID = "a" * 24


class FakeCollector:
    def collect(self, item_id: str) -> CollectedProduct:
        return CollectedProduct(
            item_id=item_id,
            product=NormalizedProduct(
                title="开学第一课 PPT",
                shop_id="shop-1",
                shop_name="测试店铺",
                price_cents=990,
                sold_reported=100,
            ),
            source="public_api",
            response_hash="fixture-hash",
        )


class RankingCollector:
    def __init__(self) -> None:
        self.calls: dict[str, int] = {}

    def collect(self, item_id: str) -> CollectedProduct:
        call = self.calls.get(item_id, 0)
        self.calls[item_id] = call + 1
        sold = {
            "a" * 24: (100, 200),
            "b" * 24: (100, 300),
        }[item_id][call]
        return CollectedProduct(
            item_id=item_id,
            product=NormalizedProduct(
                title=f"商品 {item_id[0]}",
                shop_id="shop-1",
                shop_name="测试店铺",
                price_cents=990,
                sold_reported=sold,
            ),
            source="public_api",
            response_hash=f"fixture-{item_id[0]}-{call}",
        )


class FailingAfterSuccessCollector:
    def __init__(self) -> None:
        self.calls = 0

    def collect(self, item_id: str) -> CollectedProduct:
        self.calls += 1
        if self.calls == 2:
            raise CollectionError("network_error", "offline")
        return FakeCollector().collect(item_id)


class ApiClient:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as async_client:
                return await async_client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str) -> httpx.Response:
        return self.request("GET", path)

    def post(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)


def client(tmp_path: Path) -> ApiClient:
    app = create_app(
        Settings(data_dir=tmp_path),
        collector=FakeCollector(),
        clock=lambda: NOW,
    )
    return ApiClient(app)


def test_status_reports_empty_local_database(tmp_path: Path) -> None:
    response = client(tmp_path).get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["product_count"] == 0
    assert payload["snapshot_count"] == 0
    assert payload["last_collection"] is None
    assert payload["database_bytes"] > 0


def test_import_returns_ready_duplicate_and_error_results(tmp_path: Path) -> None:
    test_client = client(tmp_path)

    response = test_client.post(
        "/api/products/import",
        json={"input_text": f"{ITEM_ID}\n{ITEM_ID}\n非法输入"},
    )

    assert response.status_code == 200
    assert [item["status"] for item in response.json()] == [
        "ready",
        "duplicate",
        "error",
    ]
    products = test_client.get("/api/products").json()
    assert len(products) == 1
    assert products[0]["item_id"] == ITEM_ID
    assert products[0]["data_status"] == "awaiting_baseline"


def test_updates_and_reads_manual_product_decision(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    test_client.post("/api/products/import", json={"input_text": ITEM_ID})

    response = test_client.patch(
        f"/api/products/{ITEM_ID}/decision",
        json={
            "decision_status": "reviewing",
            "audience": "新学期教师",
            "scenario": "开学第一课",
            "problem": "备课时间不足",
            "delivery": "可编辑 PPT",
            "notes": "核对差评",
            "next_action": "拆解三篇竞品笔记",
        },
    )

    assert response.status_code == 200
    detail = test_client.get(f"/api/products/{ITEM_ID}").json()
    assert detail["decision_status"] == "reviewing"
    assert detail["audience"] == "新学期教师"
    assert detail["next_action"] == "拆解三篇竞品笔记"


def test_missing_product_returns_404(tmp_path: Path) -> None:
    response = client(tmp_path).get(f"/api/products/{'f' * 24}")

    assert response.status_code == 404


def test_manual_collection_updates_status_and_product_snapshot(tmp_path: Path) -> None:
    test_client = client(tmp_path)
    test_client.post("/api/products/import", json={"input_text": ITEM_ID})

    response = test_client.post("/api/collections", json={"trigger": "manual"})

    assert response.status_code == 200
    assert response.json()["success_count"] == 1
    status = test_client.get("/api/status").json()
    assert status["snapshot_count"] == 1
    assert status["last_collection"]["status"] == "succeeded"
    detail = test_client.get(f"/api/products/{ITEM_ID}").json()
    assert detail["title"] == "开学第一课 PPT"
    assert detail["trusted_high_water"] == 100
    assert detail["snapshots"][0]["sold_reported"] == 100


def test_collection_rejects_unknown_trigger(tmp_path: Path) -> None:
    response = client(tmp_path).post(
        "/api/collections", json={"trigger": "whenever"}
    )

    assert response.status_code == 422


def test_complete_daily_products_are_returned_in_product_value_order(
    tmp_path: Path,
) -> None:
    current = NOW
    application = create_app(
        Settings(data_dir=tmp_path),
        collector=RankingCollector(),
        clock=lambda: current,
    )
    test_client = ApiClient(application)
    test_client.post(
        "/api/products/import",
        json={"input_text": f"{'a' * 24}\n{'b' * 24}"},
    )
    test_client.post("/api/collections", json={"trigger": "manual"})
    current += timedelta(hours=24)
    test_client.post("/api/collections", json={"trigger": "daily"})

    products = test_client.get("/api/products").json()

    assert [product["item_id"] for product in products] == ["b" * 24, "a" * 24]


def test_latest_product_failure_is_visible_without_losing_trusted_data(
    tmp_path: Path,
) -> None:
    current = NOW
    application = create_app(
        Settings(data_dir=tmp_path),
        collector=FailingAfterSuccessCollector(),
        clock=lambda: current,
    )
    test_client = ApiClient(application)
    test_client.post("/api/products/import", json={"input_text": ITEM_ID})
    test_client.post("/api/collections", json={"trigger": "manual"})
    current += timedelta(hours=1)

    test_client.post("/api/collections", json={"trigger": "manual"})
    product = test_client.get("/api/products").json()[0]
    detail = test_client.get(f"/api/products/{ITEM_ID}").json()

    assert product["data_status"] == "collection_error"
    assert product["trusted_high_water"] == 100
    assert product["last_error"]["error_type"] == "network_error"
    assert len(detail["failures"]) == 1
    assert detail["failures"][0]["error_message"] == "offline"
