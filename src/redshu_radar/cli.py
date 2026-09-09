import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from fastapi import FastAPI
import uvicorn

from redshu_radar import __version__
from redshu_radar.collectors.base import ProductCollector
from redshu_radar.collectors.public_api import default_public_api_collector
from redshu_radar.config import Settings
from redshu_radar.services.collection_service import CollectionService
from redshu_radar.services.scheduling import daily_anchor_due
from redshu_radar.storage.database import Database
from redshu_radar.storage.repositories import CollectionRepository, ProductRepository
from redshu_radar.web.app import create_app


ServeFunction = Callable[[FastAPI, str, int], None]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="redshu-radar")
    parser.add_argument(
        "--version",
        action="version",
        version=f"redshu-radar {__version__}",
    )
    parser.add_argument("--data-dir", type=Path, default=Settings().data_dir)
    commands = parser.add_subparsers(dest="command")
    collect = commands.add_parser("collect", help="采集所有启用商品")
    collect.add_argument(
        "--trigger",
        choices=("daily", "hourly", "manual", "recovery"),
        default="manual",
    )
    web = commands.add_parser("web", help="启动本地看板")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    return parser


def _serve(app: FastAPI, host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port)


def main(
    argv: Sequence[str] | None = None,
    *,
    collector: ProductCollector | None = None,
    clock: Callable[[], datetime] | None = None,
    serve: ServeFunction | None = None,
) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    active_clock = clock or (lambda: datetime.now(UTC))
    settings = Settings(data_dir=args.data_dir)

    if args.command == "collect":
        database = Database(settings.database_path)
        database.initialize()
        products = ProductRepository(database)
        collections = CollectionRepository(database)
        service = CollectionService(
            products,
            collections,
            collector or default_public_api_collector(),
        )
        summary = service.collect_all(args.trigger, captured_at=active_clock())
        print(json.dumps(asdict(summary), ensure_ascii=False))
        return 0

    if args.command == "web":
        active_collector = collector or default_public_api_collector()
        database = Database(settings.database_path)
        database.initialize()
        products = ProductRepository(database)
        collections = CollectionRepository(database)
        now = active_clock()
        latest_success = collections.latest_successful_run()
        if products.count() and daily_anchor_due(
            latest_success.started_at if latest_success else None,
            now,
        ):
            CollectionService(products, collections, active_collector).collect_all(
                "recovery", captured_at=now
            )
        application = create_app(
            settings, collector=active_collector, clock=active_clock
        )
        (serve or _serve)(application, args.host, args.port)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
