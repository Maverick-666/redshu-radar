import json
from datetime import UTC, datetime
from pathlib import Path

from redshu_radar.cli import main
from redshu_radar.collectors.base import CollectedProduct
from redshu_radar.collectors.models import NormalizedProduct
from redshu_radar.storage.database import Database
from redshu_radar.storage.repositories import ProductRepository


ITEM_ID = "a" * 24
NOW = datetime(2026, 9, 9, 0, 2, tzinfo=UTC)


class FakeCollector:
    def collect(self, item_id: str) -> CollectedProduct:
        return CollectedProduct(
            item_id,
            NormalizedProduct("测试商品", None, "测试店铺", 990, 100),
            "public_api",
            "fixture-hash",
        )


def test_collect_command_writes_snapshot_and_prints_summary(
    tmp_path: Path, capsys
) -> None:
    database = Database(tmp_path / "redshu-radar.sqlite3")
    database.initialize()
    ProductRepository(database).add(ITEM_ID, ITEM_ID, None, NOW)

    exit_code = main(
        ["--data-dir", str(tmp_path), "collect", "--trigger", "daily"],
        collector=FakeCollector(),
        clock=lambda: NOW,
    )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 0
    assert summary["status"] == "succeeded"


def test_web_command_can_be_parsed_without_starting_server(tmp_path: Path) -> None:
    calls: list[tuple[str, int]] = []

    exit_code = main(
        ["--data-dir", str(tmp_path), "web", "--host", "127.0.0.1", "--port", "9000"],
        serve=lambda app, host, port: calls.append((host, port)),
    )

    assert exit_code == 0
    assert calls == [("127.0.0.1", 9000)]
