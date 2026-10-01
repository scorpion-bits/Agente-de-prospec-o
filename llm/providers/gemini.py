"""Gemini via REST (``generateContent``). Duas chaves, dois provedores com regras diferentes:

- ``gemini-free`` (AI Studio, free tier): o Google pode usar as entradas → **só dados públicos**.
- ``gemini-paid`` (projeto com faturamento/créditos do AI Pro): dados não usados para treino →
  aceita ``internal``. Custo vai para o teto de créditos, à parte do dinheiro novo.
"""

from __future__ import annotations

import base64

from django.conf import settings

from llm.providers.base import Provider
from llm.types import DataClass, ProviderError, ProviderRequest, ProviderResponse

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(Provider):
    supports_pdf = True  # entrada nativa de PDF, inclusive escaneado (llm-strategy.md)

    def __init__(self, paid: bool, client=None):
        super().__init__(client)
        self.paid = paid
        self.name = "gemini-paid" if paid else "gemini-free"
        self.billing = "credits" if paid else "free"

    @property
    def api_key(self) -> str:
        return settings.GEMINI_API_KEY_PAID if self.paid else settings.GEMINI_API_KEY_FREE

    def available(self) -> bool:
        return bool(self.api_key)

    def accepts(self, data_class: DataClass) -> bool:
        return self.paid or data_class == DataClass.PUBLIC

    def complete(self, model: str, request: ProviderRequest) -> ProviderResponse:
        parts = [{"text": request.prompt}]
        if request.pdf_bytes:
            data = base64.b64encode(request.pdf_bytes).decode("ascii")
            parts.insert(0, {"inline_data": {"mime_type": "application/pdf", "data": data}})
        payload = {
            "systemInstruction": {"parts": [{"text": request.system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": request.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        body = self.post_json(
            f"{BASE_URL}/{model}:generateContent",
            headers={"x-goog-api-key": self.api_key},
            payload=payload,
        )
        try:
            texts = [p["text"] for p in body["candidates"][0]["content"]["parts"] if "text" in p]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("gemini: resposta vazia ou bloqueada") from None
        if not texts:
            raise ProviderError("gemini: resposta sem texto")
        usage = body.get("usageMetadata") or {}
        # Tokens de "raciocínio" são cobrados como saída.
        output = int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
        return ProviderResponse("".join(texts), int(usage.get("promptTokenCount", 0)), output)
