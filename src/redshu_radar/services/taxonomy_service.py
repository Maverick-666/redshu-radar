from datetime import datetime

from redshu_radar.domain import Category, Tag
from redshu_radar.storage.repositories import (
    CategoryRepository,
    ProductRepository,
    TagRepository,
)


class TaxonomyValidationError(ValueError):
    pass


def _normalize_name(name: str) -> tuple[str, str]:
    display_name = " ".join(name.split())
    if not display_name:
        raise TaxonomyValidationError("名称不能为空")
    return display_name, display_name.casefold()


class TaxonomyService:
    def __init__(
        self,
        categories: CategoryRepository,
        tags: TagRepository,
        products: ProductRepository,
    ) -> None:
        self.categories = categories
        self.tags = tags
        self.products = products

    def create_track(self, name: str, *, created_at: datetime) -> Category:
        display_name, normalized_name = _normalize_name(name)
        return self.categories.add(
            name=display_name,
            normalized_name=normalized_name,
            parent_id=None,
            created_at=created_at,
        )

    def create_subcategory(
        self,
        name: str,
        *,
        parent_id: int,
        created_at: datetime,
    ) -> Category:
        parent = self.categories.get(parent_id)
        if parent is None or parent.parent_id is not None:
            raise TaxonomyValidationError("细分品类的父级必须是赛道")
        display_name, normalized_name = _normalize_name(name)
        return self.categories.add(
            name=display_name,
            normalized_name=normalized_name,
            parent_id=parent.id,
            created_at=created_at,
        )

    def create_tag(self, name: str, *, created_at: datetime) -> Tag:
        display_name, normalized_name = _normalize_name(name)
        return self.tags.add(
            name=display_name,
            normalized_name=normalized_name,
            created_at=created_at,
        )

    def set_product_taxonomy(
        self,
        item_id: str,
        *,
        category_id: int | None,
        tag_ids: list[int],
    ) -> None:
        unique_tag_ids = list(dict.fromkeys(tag_ids))
        error = self.products.replace_taxonomy(
            item_id,
            category_id=category_id,
            tag_ids=unique_tag_ids,
        )
        if error == "product":
            raise TaxonomyValidationError("商品不存在")
        if error == "category":
            raise TaxonomyValidationError("商品分类必须是细分品类")
        if error == "tags":
            raise TaxonomyValidationError("标签不存在")
