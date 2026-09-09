import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from redshu_radar.parsing.short_links import resolve_short_link


ITEM_ID_PATTERN = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{24})(?![0-9a-fA-F])")
PRODUCT_PATH_PATTERN = re.compile(
    r"/(?:goods-detail|goods)/([0-9a-fA-F]{24})(?=/|$)"
)
URL_PATTERN = re.compile(r"https?://[^\s<>]+")
TRAILING_PUNCTUATION = ").,，。；;！!？?]】"


class InputParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedItem:
    item_id: str
    source_url: str | None


@dataclass(frozen=True)
class BatchInputResult:
    line_number: int
    original_input: str
    status: Literal["ready", "duplicate", "error"]
    item_id: str | None = None
    source_url: str | None = None
    message: str = ""


def _is_xhs_host(hostname: str | None) -> bool:
    return hostname == "xiaohongshu.com" or bool(
        hostname and hostname.endswith(".xiaohongshu.com")
    )


def _is_short_host(hostname: str | None) -> bool:
    return hostname == "xhslink.com" or bool(hostname and hostname.endswith(".xhslink.com"))


def _urls_in(text: str) -> list[str]:
    return [match.group(0).rstrip(TRAILING_PUNCTUATION) for match in URL_PATTERN.finditer(text)]


def extract_item_id(raw_input: str) -> ParsedItem:
    text = raw_input.strip()
    if not text:
        raise InputParseError("输入为空")

    if ITEM_ID_PATTERN.fullmatch(text):
        return ParsedItem(item_id=text.lower(), source_url=None)

    xhs_urls: list[str] = []
    disallowed_url_with_id = False
    for url in _urls_in(text):
        hostname = urlsplit(url).hostname
        if _is_short_host(hostname):
            raise InputParseError("短链需要先解析")
        if _is_xhs_host(hostname):
            xhs_urls.append(url)
        elif ITEM_ID_PATTERN.search(url):
            disallowed_url_with_id = True

    if disallowed_url_with_id and not xhs_urls:
        raise InputParseError("商品链接必须来自小红书域名")

    path_matches = [
        (match.group(1).lower(), url)
        for url in xhs_urls
        for match in PRODUCT_PATH_PATTERN.finditer(urlsplit(url).path)
    ]
    path_item_ids = {item_id for item_id, _ in path_matches}
    if len(path_item_ids) > 1:
        raise InputParseError("一行中发现多个商品 ID")
    if path_item_ids:
        item_id = path_item_ids.pop()
        matching_urls = {url for matched_id, url in path_matches if matched_id == item_id}
        source_url = matching_urls.pop() if len(matching_urls) == 1 else None
        return ParsedItem(item_id=item_id, source_url=source_url)

    search_text = " ".join(xhs_urls) if xhs_urls else text
    item_ids = {match.group(1).lower() for match in ITEM_ID_PATTERN.finditer(search_text)}
    if len(item_ids) > 1:
        raise InputParseError("一行中发现多个商品 ID")
    if not item_ids:
        raise InputParseError("无法识别小红书商品 ID")

    source_url = xhs_urls[0] if len(xhs_urls) == 1 else None
    return ParsedItem(item_id=item_ids.pop(), source_url=source_url)


def parse_batch_inputs(
    raw_input: str,
    *,
    short_link_resolver: Callable[[str], str] = resolve_short_link,
) -> list[BatchInputResult]:
    results: list[BatchInputResult] = []
    seen: set[str] = set()

    for line_number, line in enumerate(raw_input.splitlines(), start=1):
        original = line.strip()
        if not original:
            continue
        try:
            short_urls = [
                url for url in _urls_in(original) if _is_short_host(urlsplit(url).hostname)
            ]
            if len(short_urls) > 1:
                raise InputParseError("一行中发现多个小红书短链")
            parsed = (
                extract_item_id(short_link_resolver(short_urls[0]))
                if short_urls
                else extract_item_id(original)
            )
            status: Literal["ready", "duplicate", "error"] = (
                "duplicate" if parsed.item_id in seen else "ready"
            )
            seen.add(parsed.item_id)
            results.append(
                BatchInputResult(
                    line_number=line_number,
                    original_input=original,
                    status=status,
                    item_id=parsed.item_id,
                    source_url=parsed.source_url,
                    message="重复商品" if status == "duplicate" else "",
                )
            )
        except (InputParseError, ValueError) as exc:
            results.append(
                BatchInputResult(
                    line_number=line_number,
                    original_input=original,
                    status="error",
                    message=str(exc),
                )
            )

    return results
