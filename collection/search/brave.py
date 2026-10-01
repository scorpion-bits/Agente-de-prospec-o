"""Brave Search API. Formato conforme a documentação pública; **não testado contra a API real**."""

from collection.search.base import SearchProvider, SearchResult

ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider(SearchProvider):
    name = "brave"

    def _request(self, query, num):
        data = self._call(
            "GET",
            ENDPOINT,
            headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            params={"q": query, "country": "BR", "search_lang": "pt", "count": min(num, 20)},
        )
        return [
            SearchResult(item.get("title", ""), item["url"], item.get("description", ""))
            for item in data.get("web", {}).get("results", [])
            if item.get("url")
        ]
