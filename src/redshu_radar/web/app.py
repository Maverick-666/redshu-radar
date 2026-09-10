from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from redshu_radar.collectors.base import ProductCollector
from redshu_radar.collectors.public_api import default_public_api_collector
from redshu_radar.config import Settings
from redshu_radar.services.collection_service import CollectionService
from redshu_radar.services.product_service import ProductService
from redshu_radar.services.radar_service import RadarService
from redshu_radar.storage.database import Database
from redshu_radar.storage.repositories import CollectionRepository, ProductRepository
from redshu_radar.web.schemas import CollectionRequest, DecisionUpdate, ImportRequest


def create_app(
    settings: Settings | None = None,
    *,
    collector: ProductCollector | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    active_settings = settings or Settings()
    active_clock = clock or (lambda: datetime.now(UTC))
    database = Database(active_settings.database_path)
    database.initialize()
    products = ProductRepository(database)
    collections = CollectionRepository(database)
    product_service = ProductService(products)
    collection_service = CollectionService(
        products, collections, collector or default_public_api_collector()
    )
    radar_service = RadarService(products, collections, active_settings.database_path)
    app = FastAPI(title="红薯雷达", version="0.1.0")
    web_root = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=web_root / "templates")
    app.mount("/static", StaticFiles(directory=web_root / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request=request, name="index.html")

    @app.get("/api/status")
    def status() -> dict[str, object]:
        return radar_service.status()

    @app.get("/api/products")
    def list_products() -> list[dict[str, object]]:
        return radar_service.list_products()

    @app.post("/api/products/import")
    def import_products(request: ImportRequest) -> list[object]:
        return product_service.import_inputs(
            request.input_text, observed_at=active_clock()
        )

    @app.get("/api/products/{item_id}")
    def product_detail(item_id: str) -> dict[str, object]:
        detail = radar_service.product_detail(item_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="商品不存在")
        return detail

    @app.patch("/api/products/{item_id}/decision")
    def update_decision(
        item_id: str, request: DecisionUpdate
    ) -> dict[str, object]:
        updated = products.update_decision(
            item_id,
            **request.model_dump(),
            updated_at=active_clock(),
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="商品不存在")
        detail = radar_service.product_detail(item_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="商品不存在")
        return detail

    @app.post("/api/collections")
    def collect(request: CollectionRequest) -> object:
        return collection_service.collect_all(
            request.trigger,
            captured_at=active_clock(),
            item_ids=request.item_ids,
        )

    return app
