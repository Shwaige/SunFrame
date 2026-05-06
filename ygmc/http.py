import os
import threading
import time
import urllib.request
from http.cookiejar import CookieJar
from urllib.parse import urlencode, urljoin

from ygmc.config import BASE_URL, DEFAULT_REQUEST_INTERVAL, DEFAULT_RETRIES, DEFAULT_TIMEOUT, DEFAULT_USER_AGENT


_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


def _request_interval() -> float:
    raw_value = os.environ.get("YGMC_REQUEST_INTERVAL", "").strip()
    if not raw_value:
        return DEFAULT_REQUEST_INTERVAL
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return DEFAULT_REQUEST_INTERVAL


def _throttle_request() -> None:
    global _LAST_REQUEST_AT
    interval = _request_interval()
    if interval <= 0:
        return
    with _REQUEST_LOCK:
        now = time.monotonic()
        wait_seconds = interval - (now - _LAST_REQUEST_AT)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        _LAST_REQUEST_AT = time.monotonic()


class HttpClient:
    def __init__(self) -> None:
        self._cookie_jar = CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self.last_url = ""

    def fetch(
        self,
        path: str,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        url = urljoin(BASE_URL, path)
        if params:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{urlencode(params)}"
        request_headers = {"User-Agent": DEFAULT_USER_AGENT}
        if headers:
            request_headers.update(headers)
        request_data = urlencode(data).encode("utf-8") if data else None
        for attempt in range(DEFAULT_RETRIES + 1):
            req = urllib.request.Request(url, data=request_data, headers=request_headers)
            try:
                _throttle_request()
                with self._opener.open(req, timeout=DEFAULT_TIMEOUT) as resp:
                    self.last_url = resp.geturl()
                    return resp.read().decode("utf-8", errors="replace")
            except TimeoutError:
                if attempt >= DEFAULT_RETRIES:
                    raise
                print(f"HTTP请求超时，重试={attempt + 1}|url={url}")
        raise RuntimeError("HTTP请求失败")

    def cookie_value(self, name: str) -> str:
        for cookie in self._cookie_jar:
            if cookie.name == name:
                return cookie.value
        return ""
