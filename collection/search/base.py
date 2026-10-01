"""Contrato dos provedores de busca: cache permanente por consulta e teto de chamadas pagas.

Uma consulta nunca é repetida: o resultado fica em `SearchQuery`
(docs/research/ai-models-and-costs.md).
Só chamadas que **vão à rede** contam para o teto; acerto de cache é de graça. Falha (cota, chave
inválida, rede) levanta `SearchError` e **não** grava nada no cache: a consulta pode ser repetida.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from collection.models import SearchQuery
from core.services.normalize import name_key

DEFAULT_RESULTS = 10


class SearchError(Exception):
    """Falha ao consultar o provedor (configuração, cota, rede ou resposta inesperada)."""


class SearchBudgetExceeded(SearchError):
    """O teto de chamadas da execução foi atingido."""


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""

    def to_json(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


class SearchProvider:
    """Base: subclasses implementam `_request`; `search` cuida de cache e orçamento."""

    name = "base"

    def __init__(self, api_key: str, *, client: httpx.Client | None = None, max_calls=None):
        if not api_key:
            raise SearchError(f"Chave de API do provedor {self.name!r} não configurada (.env).")
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=20.0)
        self.max_calls = max_calls
        self.calls = 0  # chamadas à rede nesta instância
        self.cache_hits = 0

    def close(self):
        self.client.close()

    @staticmethod
    def query_key(query: str) -> str:
        return name_key(query)[:300]

    def search(self, query: str, *, num: int = DEFAULT_RESULTS) -> list[SearchResult]:
        key = self.query_key(query)
        if not key:
            raise SearchError("Consulta vazia.")
        cached = SearchQuery.objects.filter(provider=self.name, query_key=key).first()
        if cached is not None:
            self.cache_hits += 1
            return [SearchResult(**item) for item in cached.results]
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise SearchBudgetExceeded(f"Teto de {self.max_calls} buscas por execução atingido.")
        self.calls += 1
        results = self._request(query, num)
        SearchQuery.objects.create(
            provider=self.name,
            query_key=key,
            query=query[:300],
            results=[r.to_json() for r in results],
        )
        return results

    def _request(self, query: str, num: int) -> list[SearchResult]:  # pragma: no cover
        raise NotImplementedError

    def _check(self, response: httpx.Response):
        if response.status_code in (401, 403):
            raise SearchError(f"{self.name}: chave recusada (HTTP {response.status_code}).")
        if response.status_code in (402, 429):
            raise SearchError(f"{self.name}: cota esgotada (HTTP {response.status_code}).")
        if response.status_code != 200:
            raise SearchError(f"{self.name}: HTTP {response.status_code}.")

    def _call(self, method: str, url: str, **kwargs) -> dict:
        try:
            response = self.client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise SearchError(f"{self.name}: falha de rede ({type(exc).__name__}).") from exc
        self._check(response)
        try:
            return response.json()
        except ValueError as exc:
            raise SearchError(f"{self.name}: resposta não é JSON.") from exc
