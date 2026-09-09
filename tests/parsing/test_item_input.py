import pytest

from redshu_radar.parsing.item_input import (
    InputParseError,
    extract_item_id,
    parse_batch_inputs,
)


ITEM_ID = "6a37ecb45200e70001a2b26a"


@pytest.mark.parametrize(
    ("raw_input", "expected_url"),
    [
        (ITEM_ID, None),
        (
            f"https://www.xiaohongshu.com/goods-detail/{ITEM_ID}?source=share",
            f"https://www.xiaohongshu.com/goods-detail/{ITEM_ID}?source=share",
        ),
        (
            f"复制这段分享文案 https://mall.xiaohongshu.com/goods/{ITEM_ID} 打开看看",
            f"https://mall.xiaohongshu.com/goods/{ITEM_ID}",
        ),
    ],
)
def test_extracts_supported_product_inputs(
    raw_input: str, expected_url: str | None
) -> None:
    parsed = extract_item_id(raw_input)

    assert parsed.item_id == ITEM_ID
    assert parsed.source_url == expected_url


def test_rejects_ambiguous_input_with_multiple_product_ids() -> None:
    with pytest.raises(InputParseError, match="多个商品 ID"):
        extract_item_id(f"{ITEM_ID} {'b' * 24}")


def test_rejects_non_xiaohongshu_url() -> None:
    with pytest.raises(InputParseError, match="小红书"):
        extract_item_id(f"https://example.com/goods/{ITEM_ID}")


def test_batch_ignores_blank_lines_and_marks_duplicates() -> None:
    result = parse_batch_inputs(f"\n{ITEM_ID}\n{ITEM_ID.upper()}\n非法输入\n")

    assert [item.status for item in result] == ["ready", "duplicate", "error"]
    assert result[0].item_id == ITEM_ID
    assert result[1].item_id == ITEM_ID
    assert "无法识别" in result[2].message


def test_batch_resolves_xhs_short_link_before_extracting_id() -> None:
    short_url = "https://xhslink.com/a1b2c3"
    resolved_url = f"https://www.xiaohongshu.com/goods-detail/{ITEM_ID}"
    calls: list[str] = []

    def resolver(url: str) -> str:
        calls.append(url)
        return resolved_url

    result = parse_batch_inputs(short_url, short_link_resolver=resolver)

    assert calls == [short_url]
    assert result[0].status == "ready"
    assert result[0].item_id == ITEM_ID
    assert result[0].source_url == resolved_url
