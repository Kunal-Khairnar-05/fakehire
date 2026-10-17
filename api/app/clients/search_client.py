"""Web search through the Tavily API (POST https://api.tavily.com/search).

Only short identifiers are ever sent (a company name, a phone number, an email address),
never the whole posting a user pasted.
"""
from dataclasses import dataclass

import httpx

TAVILY_URL = "https://api.tavily.com/search"


class SearchUnavailable(Exception):
    """No API key, quota used up, timeout, or the provider is down."""


@dataclass
class SearchResult:
    title: str
    url: str
    content: str


class SearchClient:
    def __init__(self, api_key: str | None, timeout: float):
        self.api_key = api_key
        self._http = httpx.Client(timeout=timeout)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if not self.enabled:
            raise SearchUnavailable("no TAVILY_API_KEY configured")
        try:
            response = self._http.post(
                TAVILY_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"query": query, "search_depth": "basic", "max_results": max_results},  # basic = 1 credit
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:   # 401 bad key, 429/432 quota, timeouts, network errors
            raise SearchUnavailable(str(exc)) from exc
        return [SearchResult(r.get("title", ""), r.get("url", ""), r.get("content", ""))
                for r in response.json().get("results", [])]

    def close(self) -> None:
        self._http.close()
