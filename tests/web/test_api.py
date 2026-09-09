import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI

from redshu_radar.collectors.base import CollectedProduct
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
