import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from redshu_radar.collectors.base import HttpResponse


class UrllibTransport:
    name = "urllib"

    def get(self, url: str, timeout: float) -> HttpResponse:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with build_opener().open(request, timeout=timeout) as response:
                return HttpResponse(status=response.status, body=response.read())
        except HTTPError as exc:
            return HttpResponse(status=exc.code, body=exc.read())
        except URLError as exc:
            raise OSError(str(exc.reason)) from exc


class CurlTransport:
    name = "curl"

    def __init__(self, executable: str = "/usr/bin/curl") -> None:
        self.executable = executable

    def get(self, url: str, timeout: float) -> HttpResponse:
        result = subprocess.run(
            [
                self.executable,
                "--silent",
                "--show-error",
                "--location",
                "--max-time",
                str(timeout),
                "--write-out",
                "\n%{http_code}",
                url,
            ],
            capture_output=True,
            check=False,
            timeout=timeout + 2,
        )
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", errors="replace").strip()
            raise OSError(message or f"curl exited with {result.returncode}")
        body, separator, status_text = result.stdout.rpartition(b"\n")
        if not separator or not status_text.isdigit():
            raise OSError("curl did not return an HTTP status")
        return HttpResponse(status=int(status_text), body=body)
