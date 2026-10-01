"""Provedor falso: nenhum teste chama rede. Respostas roteirizadas, uma por chamada."""

from __future__ import annotations

from llm.providers.base import Provider
from llm.types import DataClass, LLMError, ProviderRequest, ProviderResponse


class FakeProvider(Provider):
    supports_pdf = True

    def __init__(
        self,
        replies=(),
        *,
        name="fake",
        billing="free",
        classes=(DataClass.PUBLIC, DataClass.INTERNAL),
        is_available=True,
        input_tokens=100,
        output_tokens=50,
    ):
        super().__init__(client=None)
        self.name = name
        self.billing = billing
        self.classes = tuple(classes)
        self.is_available = is_available
        self.replies = list(replies)  # str = resposta; LLMError = levanta
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.requests: list[tuple[str, ProviderRequest]] = []

    def available(self) -> bool:
        return self.is_available

    def accepts(self, data_class: DataClass) -> bool:
        return data_class in self.classes

    def complete(self, model: str, request: ProviderRequest) -> ProviderResponse:
        self.requests.append((model, request))
        reply = self.replies.pop(0) if self.replies else "{}"
        if isinstance(reply, LLMError):
            raise reply
        return ProviderResponse(reply, self.input_tokens, self.output_tokens)
