import urllib.request
from http.cookiejar import CookieJar
from urllib.parse import urlencode, urljoin

from ygmc.config import BASE_URL, DEFAULT_TIMEOUT, DEFAULT_USER_AGENT


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
        req = urllib.request.Request(url, data=request_data, headers=request_headers)
        with self._opener.open(req, timeout=DEFAULT_TIMEOUT) as resp:
            self.last_url = resp.geturl()
            return resp.read().decode("utf-8", errors="replace")

    def cookie_value(self, name: str) -> str:
        for cookie in self._cookie_jar:
            if cookie.name == name:
                return cookie.value
        return ""
