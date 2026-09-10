import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from redshu_radar.services.taxonomy_service import (
    TaxonomyService,
    TaxonomyValidationError,
)
from redshu_radar.storage.database import Database
from redshu_radar.storage.repositories import (
    CategoryRepository,
    ProductRepository,
    TagRepository,
)


@pytest.fixture
def taxonomy(
    tmp_path: Path,
) -> tuple[TaxonomyService, ProductRepository, TagRepository]:
    database = Database(tmp_path / "radar.sqlite3")
    database.initialize()
    products = ProductRepository(database)
    categories = CategoryRepository(database)
    tags = TagRepository(database)
    return TaxonomyService(categories, tags, products), products, tags


def test_category_creation_normalizes_and_reuses_sibling_names(
    taxonomy: tuple[TaxonomyService, ProductRepository, TagRepository],
) -> None:
    service, _, _ = taxonomy
    created_at = datetime(2026, 9, 10, tzinfo=UTC)

    track = service.create_track("  AI   教程  ", created_at=created_at)
    duplicate_track = service.create_track("ai 教程", created_at=created_at)
    subcategory = service.create_subcategory(
        " 提示词  教程 ", parent_id=track.id, created_at=created_at
    )
    duplicate_subcategory = service.create_subcategory(
        "提示词 教程", parent_id=track.id, created_at=created_at
    )

    assert duplicate_track == track
    assert track.name == "AI 教程"
    assert duplicate_subcategory == subcategory
    assert subcategory.parent_id == track.id


def test_category_creation_rejects_a_third_level(
    taxonomy: tuple[TaxonomyService, ProductRepository, TagRepository],
) -> None:
    service, _, _ = taxonomy
    created_at = datetime(2026, 9, 10, tzinfo=UTC)
    track = service.create_track("AI 教程", created_at=created_at)
    subcategory = service.create_subcategory(
        "提示词", parent_id=track.id, created_at=created_at
    )

    with pytest.raises(TaxonomyValidationError, match="赛道"):
        service.create_subcategory(
            "第三层", parent_id=subcategory.id, created_at=created_at
        )


def test_tag_creation_normalizes_and_reuses_names(
    taxonomy: tuple[TaxonomyService, ProductRepository, TagRepository],
) -> None:
    service, _, _ = taxonomy
    created_at = datetime(2026, 9, 10, tzinfo=UTC)

    tag = service.create_tag("  AI   提示词  ", created_at=created_at)
    duplicate = service.create_tag("ai 提示词", created_at=created_at)

    assert duplicate == tag
    assert tag.name == "AI 提示词"


def test_product_taxonomy_replaces_clears_and_deduplicates_tags(
    taxonomy: tuple[TaxonomyService, ProductRepository, TagRepository],
) -> None:
    service, products, tags = taxonomy
    created_at = datetime(2026, 9, 10, tzinfo=UTC)
    products.add("p" * 24, "input", None, created_at)
    track = service.create_track("AI 教程", created_at=created_at)
    subcategory = service.create_subcategory(
        "提示词", parent_id=track.id, created_at=created_at
    )
    evergreen = service.create_tag("常青", created_at=created_at)
    seasonal = service.create_tag("开学季", created_at=created_at)

    service.set_product_taxonomy(
        "p" * 24,
        category_id=subcategory.id,
        tag_ids=[evergreen.id, seasonal.id, evergreen.id],
    )
    service.set_product_taxonomy(
        "p" * 24,
        category_id=subcategory.id,
        tag_ids=[evergreen.id, seasonal.id],
    )

    assert products.get("p" * 24).category_id == subcategory.id
    assert tags.list_for_product("p" * 24) == [evergreen, seasonal]

    service.set_product_taxonomy("p" * 24, category_id=None, tag_ids=[])

    assert products.get("p" * 24).category_id is None
    assert tags.list_for_product("p" * 24) == []


def test_product_taxonomy_validates_and_writes_in_one_transaction(
    taxonomy: tuple[TaxonomyService, ProductRepository, TagRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, products, _ = taxonomy
    created_at = datetime(2026, 9, 10, tzinfo=UTC)
    products.add("t" * 24, "input", None, created_at)
    track = service.create_track("AI 教程", created_at=created_at)
    subcategory = service.create_subcategory(
        "提示词", parent_id=track.id, created_at=created_at
    )
    tag = service.create_tag("常青", created_at=created_at)
    original_connect = products.database.connect
    connection_count = 0

    @contextmanager
    def counted_connect() -> Iterator[sqlite3.Connection]:
        nonlocal connection_count
        connection_count += 1
        with original_connect() as connection:
            yield connection

    monkeypatch.setattr(products.database, "connect", counted_connect)

    service.set_product_taxonomy(
        "t" * 24, category_id=subcategory.id, tag_ids=[tag.id]
    )

    assert connection_count == 1


def test_product_taxonomy_rejects_track_and_preserves_previous_values(
    taxonomy: tuple[TaxonomyService, ProductRepository, TagRepository],
) -> None:
    service, products, tags = taxonomy
    created_at = datetime(2026, 9, 10, tzinfo=UTC)
    products.add("q" * 24, "input", None, created_at)
    track = service.create_track("AI 教程", created_at=created_at)
    subcategory = service.create_subcategory(
        "提示词", parent_id=track.id, created_at=created_at
    )
    tag = service.create_tag("常青", created_at=created_at)
    service.set_product_taxonomy(
        "q" * 24, category_id=subcategory.id, tag_ids=[tag.id]
    )

    with pytest.raises(TaxonomyValidationError, match="细分品类"):
        service.set_product_taxonomy(
            "q" * 24, category_id=track.id, tag_ids=[]
        )

    assert products.get("q" * 24).category_id == subcategory.id
    assert tags.list_for_product("q" * 24) == [tag]


def test_product_taxonomy_rejects_missing_tags_without_partial_update(
    taxonomy: tuple[TaxonomyService, ProductRepository, TagRepository],
) -> None:
    service, products, tags = taxonomy
    created_at = datetime(2026, 9, 10, tzinfo=UTC)
    products.add("r" * 24, "input", None, created_at)
    track = service.create_track("AI 教程", created_at=created_at)
    first = service.create_subcategory(
        "提示词", parent_id=track.id, created_at=created_at
    )
    second = service.create_subcategory(
        "AI 绘画", parent_id=track.id, created_at=created_at
    )
    tag = service.create_tag("常青", created_at=created_at)
    service.set_product_taxonomy(
        "r" * 24, category_id=first.id, tag_ids=[tag.id]
    )

    with pytest.raises(TaxonomyValidationError, match="标签"):
        service.set_product_taxonomy(
            "r" * 24, category_id=second.id, tag_ids=[tag.id, 999]
        )

    assert products.get("r" * 24).category_id == first.id
    assert tags.list_for_product("r" * 24) == [tag]
