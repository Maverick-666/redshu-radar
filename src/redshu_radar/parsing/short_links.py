from typing import Protocol
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ShortLinkResolutionError(ValueError):
    pass


class _Response(Protocol):
    def geturl(self) -> str: ...

    def __enter__(self) -> "_Response": ...

    def __exit__(self, *args: object) -> None: ...


class _Opener(Protocol):
    def open(self, request: Request, timeout: float) -> _Response: ...


class _LimitedRedirectHandler(HTTPRedirectHandler):
    max_redirections = 5


def _is_xhs_short_host(hostname: str | None) -> bool:
    return hostname == "xhslink.com" or bool(hostname and hostname.endswith(".xhslink.com"))


def resolve_short_link(
    url: str,
    *,
    opener: _Opener | None = None,
    timeout: float = 10.0,
) -> str:
    if not _is_xhs_short_host(urlsplit(url).hostname):
        raise ShortLinkResolutionError("只支持 xhslink.com 短链")

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    active_opener = opener or build_opener(_LimitedRedirectHandler())
    try:
        with active_opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
    except (OSError, TimeoutError) as exc:
        raise ShortLinkResolutionError(f"短链解析失败：{exc}") from exc

    if urlsplit(final_url).scheme not in {"http", "https"}:
        raise ShortLinkResolutionError("短链解析失败：目标地址无效")
    return final_url
