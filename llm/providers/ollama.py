"""Ollama (``/api/chat``): local por padrão; ``OLLAMA_BASE_URL`` pode apontar para outro servidor.

Um servidor **remoto** (inclusive o Ollama Cloud, se um dia for adotado) é tratado como terceiro:
só recebe dados ``public`` (LGPD). Só localhost recebe ``internal``. O Ollama Cloud não foi adotado
(ADR-033); este adapter apenas não impede essa troca de endereço.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings

from llm.providers.base import Provider
from llm.types import DataClass, ProviderError, ProviderRequest, ProviderResponse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


class OllamaProvider(Provider):
    name = "ollama"
    billing = "free"  # custo em tempo/energia, não em dinheiro

    @property
    def base_url(self) -> str:
        return settings.OLLAMA_BASE_URL.rstrip("/")

    def is_local(self) -> bool:
        return (urlparse(self.base_url).hostname or "") in LOCAL_HOSTS

    def available(self) -> bool:
        return bool(self.base_url)

    def accepts(self, data_class: DataClass) -> bool:
        return self.is_local() or data_class == DataClass.PUBLIC

    def complete(self, model: str, request: ProviderRequest) -> ProviderResponse:
        headers = {}
        if settings.OLLAMA_API_KEY:
            headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"
        payload = {
            "model": model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": request.max_output_tokens},
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
        }
        body = self.post_json(f"{self.base_url}/api/chat", headers=headers, payload=payload)
        message = body.get("message")
        text = message.get("content", "") if isinstance(message, dict) else ""
        if not text:
            raise ProviderError("ollama: resposta sem texto")
        return ProviderResponse(
            text, int(body.get("prompt_eval_count", 0)), int(body.get("eval_count", 0))
        )
