import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx

from redshu_radar.collectors.base import CollectedProduct
from redshu_radar.collectors.models import NormalizedProduct
from redshu_radar.config import Settings
from redshu_radar.web.app import create_app


class FakeCollector:
    def collect(self, item_id: str) -> CollectedProduct:
        return CollectedProduct(
            item_id=item_id,
            product=NormalizedProduct("测试商品", None, "测试店铺", 990, 100),
            source="public_api",
            response_hash="fixture-hash",
        )


def request(app: object, path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get(path)

    return asyncio.run(send())


def app(tmp_path: Path) -> object:
    return create_app(
        Settings(data_dir=tmp_path),
        collector=FakeCollector(),
        clock=lambda: datetime(2026, 9, 9, tzinfo=UTC),
    )


def test_dashboard_contains_core_workflow_and_no_demo_rows(tmp_path: Path) -> None:
    response = request(app(tmp_path), "/")

    assert response.status_code == 200
    assert "红薯雷达" in response.text
    assert "竞品监控看板" in response.text
    assert "立即采集" in response.text
    assert "添加商品" in response.text
    assert "24h 增量" in response.text
    assert "商品价值" in response.text
    assert 'id="awaiting-count"' in response.text
    assert 'id="attention-count"' in response.text
    assert "待基线" in response.text
    assert "异常" in response.text
    assert 'data-filter="cross_period"' in response.text
    assert "暂无商品" in response.text
    assert "开学第一课 PPT" not in response.text


def test_dashboard_links_static_assets(tmp_path: Path) -> None:
    application = app(tmp_path)
    page = request(application, "/")
    styles = request(application, "/static/styles.css")
    script = request(application, "/static/app.js")

    assert '/static/styles.css' in page.text
    assert '/static/app.js' in page.text
    assert styles.status_code == 200
    assert "--text: #17231c" in styles.text
    assert "color: var(--text)" in styles.text
    assert script.status_code == 200
    assert '"/api/status"' in script.text
    assert '"/api/products/import"' in script.text
    assert '"/api/collections"' in script.text
    assert "baseline_snapshot_id" in script.text
    assert "current_snapshot_id" in script.text
    assert "interval_hours" in script.text
    assert 'data_status === "complete_daily"' in script.text
    assert 'const readyItemIds = results' in script.text
    assert 'item_ids: readyItemIds' in script.text
    assert '$("#awaiting-count")' in script.text


def test_dashboard_has_add_and_detail_drawers(tmp_path: Path) -> None:
    response = request(app(tmp_path), "/")

    assert 'id="add-drawer"' in response.text
    assert 'id="detail-drawer"' in response.text
    assert "分享文案、商品链接或 24 位商品 ID" in response.text
    assert "人群" in response.text
    assert "下一步动作" in response.text
    assert "采集失败记录" in response.text

    script = request(app(tmp_path), "/static/app.js")
    assert "product.failures" in script.text


def test_narrow_browser_keeps_toolbar_and_drawers_visible(tmp_path: Path) -> None:
    styles = request(app(tmp_path), "/static/styles.css").text

    assert "body { margin: 0; background: var(--bg)" in styles
    assert "@media (max-width: 900px)" in styles
    assert ".toolbar { flex-wrap: wrap; }" in styles
    assert ".drawer.wide { width: min(620px, 100vw); }" in styles
