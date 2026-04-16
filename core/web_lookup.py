from __future__ import annotations

import html
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlparse


SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"


def _decode_result_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        redirect = parse_qs(parsed.query).get("uddg", [""])[0]
        if redirect:
            return unquote(redirect)
    return raw_url


class DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self, max_results: int) -> None:
        super().__init__()
        self.max_results = max_results
        self.results: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        css_class = attr_map.get("class", "")
        if tag == "a" and "result__a" in css_class:
            self._finalize_current()
            self.current = {
                "title": "",
                "url": _decode_result_url(attr_map.get("href", "")),
                "snippet": "",
            }
            self.capture = "title"
            return
        if self.current and "result__snippet" in css_class:
            self.capture = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if self.capture == "title" and tag == "a":
            self.capture = None
        elif self.capture == "snippet" and tag in {"a", "div", "span"}:
            self.capture = None

    def handle_data(self, data: str) -> None:
        if not self.current or not self.capture:
            return
        text = " ".join(data.split())
        if not text:
            return
        existing = self.current[self.capture]
        self.current[self.capture] = f"{existing} {text}".strip()

    def close(self) -> None:
        super().close()
        self._finalize_current()

    def _finalize_current(self) -> None:
        if not self.current:
            return
        title = html.unescape(self.current.get("title", "")).strip()
        url = self.current.get("url", "").strip()
        snippet = html.unescape(self.current.get("snippet", "")).strip()
        if title and url and len(self.results) < self.max_results:
            self.results.append({"title": title, "url": url, "snippet": snippet})
        self.current = None
        self.capture = None


def search_web(query: str, *, max_results: int = 5, timeout: float = 5.0) -> list[dict[str, str]]:
    normalized_query = " ".join((query or "").split())
    if not normalized_query:
        raise ValueError("Consulta vazia.")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("O pacote 'requests' nao esta instalado no ambiente atual.") from exc

    safe_max_results = max(1, min(int(max_results or 5), 10))
    response = requests.get(
        SEARCH_ENDPOINT,
        params={"q": normalized_query},
        headers={"User-Agent": "Nexus-Agent"},
        timeout=timeout,
    )
    response.raise_for_status()

    parser = DuckDuckGoHTMLParser(max_results=safe_max_results)
    parser.feed(response.text)
    parser.close()
    return parser.results
