from io import BytesIO

import pytest

from redshu_radar.parsing.short_links import (
    ShortLinkResolutionError,
    resolve_short_link,
)


class FakeResponse(BytesIO):
    def __init__(self, final_url: str) -> None:
        super().__init__(b"")
        self.final_url = final_url

    def geturl(self) -> str:
        return self.final_url

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class FakeOpener:
    def __init__(self, final_url: str) -> None:
        self.final_url = final_url
        self.requested_url: str | None = None
        self.timeout: float | None = None

    def open(self, request: object, timeout: float) -> FakeResponse:
        self.requested_url = request.full_url  # type: ignore[attr-defined]
        self.timeout = timeout
        return FakeResponse(self.final_url)


def test_resolves_xhslink_to_final_url() -> None:
    final_url = "https://www.xiaohongshu.com/goods-detail/6a37ecb45200e70001a2b26a"
    opener = FakeOpener(final_url)

    result = resolve_short_link(
        "https://xhslink.com/a1b2c3", opener=opener, timeout=3.5
    )

    assert result == final_url
    assert opener.requested_url == "https://xhslink.com/a1b2c3"
    assert opener.timeout == 3.5


def test_rejects_non_xhslink_domain() -> None:
    with pytest.raises(ShortLinkResolutionError, match="xhslink.com"):
        resolve_short_link("https://example.com/a1b2c3", opener=FakeOpener("unused"))


def test_wraps_network_failures_with_clear_error() -> None:
    class FailingOpener:
        def open(self, request: object, timeout: float) -> FakeResponse:
            raise TimeoutError("timed out")

    with pytest.raises(ShortLinkResolutionError, match="短链解析失败"):
        resolve_short_link("https://xhslink.com/a1b2c3", opener=FailingOpener())
