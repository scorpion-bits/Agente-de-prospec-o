"""Serper.dev (Google SERP). Formato da documentação pública; **não testado na API real**."""

from collection.search.base import SearchProvider, SearchResult

ENDPOINT = "https://google.serper.dev/search"


class SerperProvider(SearchProvider):
    name = "serper"

    def _request(self, query, num):
        data = self._call(
            "POST",
            ENDPOINT,
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            json={"q": query, "gl": "br", "hl": "pt-br", "num": num},
        )
        return [
            SearchResult(item.get("title", ""), item["link"], item.get("snippet", ""))
            for item in data.get("organic", [])
            if item.get("link")
        ]
