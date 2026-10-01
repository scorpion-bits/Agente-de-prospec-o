"""Tipos e erros da camada de IA (E10). Nada aqui conhece fornecedor."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class DataClass(StrEnum):
    """Classe do dado enviado (llm-strategy.md, item 7).

    ``public``: documentos públicos; pode ir a free tier.
    ``internal``: contatos, interações, rascunhos com nomes; só provedor pago ou local.
    """

    PUBLIC = "public"
    INTERNAL = "internal"


@dataclass(frozen=True)
class LLMInput:
    """Entrada de uma tarefa. ``data_class`` é obrigatório: ninguém esquece de decidir."""

    data_class: DataClass
    text: str = ""
    pdf_bytes: bytes | None = None
    url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRequest:
    system: str
    prompt: str
    pdf_bytes: bytes | None = None
    max_output_tokens: int = 1500


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResult:
    data: Any  # instância do schema Pydantic da tarefa
    strategy: str  # "rules", "gemini-free:gemini-3.1-flash-lite", ...
    cost_usd: Decimal = Decimal("0")
    cached: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    unverified: list[str] = field(default_factory=list)  # campos cuja citação não foi achada


class LLMError(Exception):
    """Base dos erros da camada. As mensagens nunca carregam o conteúdo enviado ou recebido."""


class ProviderUnavailable(LLMError):
    """Sem chave ou sem suporte para esta entrada: a estratégia é pulada, não conta como erro."""


class RateLimited(LLMError):
    """429: a cota acabou; passa ao próximo provedor."""


class ProviderError(LLMError):
    """Rede, 5xx, 4xx ou resposta vazia/bloqueada."""


class SchemaValidationFailed(LLMError):
    """A resposta não é JSON do schema da tarefa."""


class BudgetExceeded(LLMError):
    """Esta chamada passaria do teto mensal ou da execução."""


class PricingError(LLMError):
    """Modelo pago sem preço na tabela: não dá para controlar o teto, então não se chama."""


class NoStrategyAvailable(LLMError):
    """Nenhuma estratégia da tarefa produziu resultado (as razões vêm na mensagem)."""
