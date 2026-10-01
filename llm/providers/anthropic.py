"""Claude via Messages API (REST). Pago, dinheiro novo; aceita dados internos (API não treina)."""

from __future__ import annotations

from django.conf import settings

from llm.providers.base import Provider
from llm.types import DataClass, ProviderError, ProviderRequest, ProviderResponse

URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicProvider(Provider):
    name = "anthropic"
    billing = "money"

    def available(self) -> bool:
        return bool(settings.ANTHROPIC_API_KEY)

    def accepts(self, data_class: DataClass) -> bool:
        return True

    def complete(self, model: str, request: ProviderRequest) -> ProviderResponse:
        payload = {
            "model": model,
            "max_tokens": request.max_output_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        body = self.post_json(
            URL,
            headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": API_VERSION},
            payload=payload,
        )
        blocks = body.get("content")
        if not isinstance(blocks, list):
            raise ProviderError("anthropic: resposta sem conteúdo")
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
        if not text:
            raise ProviderError("anthropic: resposta sem texto")
        usage = body.get("usage") or {}
        return ProviderResponse(
            text, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
        )
