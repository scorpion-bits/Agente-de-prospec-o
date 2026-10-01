"""Interface dos provedores. Cada adapter é o **único** lugar que conhece o fornecedor (ADR-003).

Falamos HTTP direto com ``httpx`` (já dependência): sem SDK, o contrato fica pequeno, os testes usam
``httpx.MockTransport`` e nenhum outro módulo do projeto importa SDK de provedor.
"""

from __future__ import annotations

import httpx

from llm.types import (
    DataClass,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    RateLimited,
)

TIMEOUT_SECONDS = 90.0


class Provider:
    name = ""
    # "free" (custo 0, sem teto) · "credits" (créditos Google AI Pro) · "money" (dinheiro novo)
    billing = "free"
    supports_pdf = False

    def __init__(self, client: httpx.Client | None = None):
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=TIMEOUT_SECONDS)
        return self._client

    def available(self) -> bool:
        """Há credencial/endereço configurado?"""
        raise NotImplementedError

    def accepts(self, data_class: DataClass) -> bool:
        """Este provedor pode receber dados desta classe? Free tier só ``public``."""
        raise NotImplementedError

    def complete(self, model: str, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError

    def post_json(self, url: str, *, headers: dict, payload: dict) -> dict:
        """POST que traduz falhas em erros da camada, sem jamais repetir corpo ou URL (chave)."""
        try:
            response = self.client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"rede: {type(exc).__name__}") from None
        if response.status_code == 429:
            raise RateLimited(f"{self.name}: HTTP 429")
        if response.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            raise ProviderError(f"{self.name}: resposta não é JSON") from None
        if not isinstance(body, dict):
            raise ProviderError(f"{self.name}: resposta inesperada")
        return body
